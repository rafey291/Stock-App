# Stock Portfolio Analytics Dashboard

![tests](https://github.com/rafey291/stock-portfolio-analytics-dashboard/actions/workflows/tests.yml/badge.svg)

An interactive web app for building a weighted stock portfolio, comparing it with the S&P 500 (or another benchmark), and seeing the risk behind the returns. It pulls live market data from Yahoo Finance and turns it into interactive charts.

**Live app:** paste your Streamlit link here after you deploy (steps are in "Deploy for free" below)

<!-- Screenshot: run the app, take a screenshot of the Portfolio vs benchmark tab, save it as docs/screenshot.png, then replace this line with:  ![Dashboard screenshot](docs/screenshot.png) -->

## What it does

- Pulls live daily prices from Yahoo Finance with yfinance, adjusted for stock splits and dividends
- Compares up to 15 tickers over a preset or custom date range
- Builds a weighted portfolio from an editable table of tickers and weights, with buy and hold or daily rebalancing
- Benchmarks the portfolio against the S&P 500 (SPY or ^GSPC), the NASDAQ 100 or the TSX Composite
- Calculates total return, annual return, volatility, Sharpe ratio, max drawdown, beta, alpha and correlation
- Draws interactive Plotly charts: growth of the starting amount, allocation, normalized performance, risk vs return, drawdown, rolling volatility, a correlation heatmap, and candlesticks with moving averages
- Handles bad input and failures: ticker typos, missing data, short price histories, Yahoo outages
- Lets you download the cleaned price data as a CSV

## How it is built

The code is split into layers. Each file has one job and does not reach into the others.

| File | Layer | Job |
| --- | --- | --- |
| `data_ingestion.py` | Data ingestion | Downloads prices from Yahoo Finance, cleans dates and timezones, caches results, collects errors |
| `processing.py` | Processing | All the math with pandas: weights, portfolio value, returns, risk metrics |
| `visualization.py` | Visualization | Turns results into Plotly figures |
| `app.py` | UI | The Streamlit page: sidebar inputs, calls the three layers, shows results |
| `config.py` | Settings | Labels, limits and defaults in one place |
| `demo_data.py` | Backup data | Simulated prices, only used when the user switches it on |
| `tests/` | Tests | Checks the math, the data cleaning and the whole page |

```
sidebar inputs -> data_ingestion.py -> processing.py -> visualization.py -> app.py (screen)
```

`processing.py` and `visualization.py` never import Streamlit, so the math and the charts can be tested on their own.

## Run it on your computer

You need Python 3.10 or newer (tested on 3.12).

**Windows**

```
py -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
venv\Scripts\python -m streamlit run app.py
```

**Mac or Linux**

```
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
venv/bin/python -m streamlit run app.py
```

The app opens at http://localhost:8501.

Calling the virtual environment's own `python` (instead of activating it) avoids PATH problems when several Python versions are installed. If you have more than one, pick one on Windows with `py -3.12 -m venv venv`.

## Run the tests

```
venv\Scripts\python -m pip install pytest
venv\Scripts\python -m pytest
```

On Mac or Linux, use `venv/bin/python` instead of `venv\Scripts\python`.

The tests need no internet. They use a fake yfinance and simulated prices to check the math against hand-worked examples and against numpy, the data cleaning, and the whole page in many normal and awkward situations (empty portfolio, duplicate tickers, a bad ticker, Yahoo being down, a stock with a short history, and more).

## Deploy for free (Streamlit Community Cloud)

1. Create a new empty public repository on GitHub named `stock-portfolio-analytics-dashboard`.
2. Push this folder to it:

   ```
   git init
   git add .
   git commit -m "Stock portfolio analytics dashboard"
   git branch -M main
   git remote add origin https://github.com/rafey291/stock-portfolio-analytics-dashboard.git
   git push -u origin main
   ```

3. Go to https://share.streamlit.io and sign in with GitHub.
4. Click **Create app** in the upper-right corner. Choose your repository, the branch `main`, and the main file `app.py`. The default Python version (3.12) is fine.
5. Click **Deploy**. The first build takes a few minutes, and the app gets a `streamlit.app` address. You can change the subdomain.
6. Paste the address at the top of this README, then commit and push. Every push to `main` redeploys the app automatically.

Tips:

- Open the link in a private window before you share it.
- Free apps can go to sleep when nobody visits for a while. Open yours a few minutes before an interview so it is awake.
- Yahoo Finance sometimes limits requests that come from shared hosting. The app remembers downloads for an hour, which helps. If prices ever fail to load, the page shows a button that switches to simulated data (clearly labeled as simulated).

## How the numbers are calculated

The same notes appear inside the app, in the "Data and method" tab.

```
daily return     = today's price / yesterday's price - 1
total return     = last value / first value - 1
annual return    = (last value / first value) ^ (252 / number of days) - 1
volatility       = standard deviation of daily returns * sqrt(252)
sharpe ratio     = (average daily return - daily risk-free rate) / standard deviation of daily returns * sqrt(252)
drawdown         = value / highest value so far - 1       (max drawdown is the lowest of these)
beta             = covariance(asset returns, benchmark returns) / variance(benchmark returns)
alpha            = (average asset excess return - beta * average benchmark excess return) * 252
correlation      = how closely two return series move together, from -1 to +1
```

Portfolio value:

```
buy and hold     = sum of (weight * price / first price) * starting amount
rebalance daily  = daily portfolio return is sum of (weight * stock daily return), then compounded
```

## Design decisions

- **Adjusted prices.** Yahoo's prices are adjusted for splits and dividends. Without that, a stock split would look like a crash.
- **Shared dates only.** All assets are lined up on the dates where every one of them has a price, so the columns match row by row. The page tells you when a young stock shortens the window.
- **SPY is the default S&P 500 benchmark.** The SPY ETF includes dividends, like the adjusted stock prices do, so the comparison is fair. The ^GSPC index is also available.
- **Caching.** Downloads are remembered for an hour, so every click does not call Yahoo again. Errors are not remembered, so a failed ticker is retried.
- **One bad ticker does not break the page.** Failures are collected per ticker and shown as a message.
- **Simulated data mode.** A backup for Yahoo outages. It always shows a warning banner so nobody mistakes it for real data.
- **Plain, readable code.** Simple loops and short functions with docstrings, so every step is easy to follow and explain.

## Limitations

- Yahoo Finance is a free, unofficial data source. Prices can be delayed, and requests can be limited.
- Returns are in each asset's own currency. There is no currency conversion, so mixing US and Canadian listings compares raw local returns.
- No trading costs, taxes or slippage are included.
- Daily prices only.

## Ideas for next steps

- Monte Carlo simulation of possible future portfolio values
- A portfolio optimizer (efficient frontier)
- Upload a CSV of holdings instead of typing them in
- Download prices for all tickers in parallel
- Currency conversion

## Disclaimer

This project is for learning. It is not financial advice, and past performance does not predict future results.
