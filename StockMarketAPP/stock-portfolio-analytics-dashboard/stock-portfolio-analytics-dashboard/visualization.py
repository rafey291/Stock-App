"""
VISUALIZATION LAYER

Job: turn numbers into interactive Plotly charts.
Every function here takes data and returns a Plotly figure. Nothing is
calculated here (that is processing.py) and nothing is shown on the page
(that is app.py), so charts are easy to change without breaking anything else.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import PORTFOLIO_NAME, RETURN_COLUMN, VOLATILITY_COLUMN

# One place for every colour, so the whole dashboard looks consistent.
COLORS = {
    "portfolio": "#1E4FD8",   # the main character of the dashboard
    "benchmark": "#7B8494",   # quiet gray, so the portfolio stands out
    "up": "#1B9E77",
    "down": "#D1453B",
    "grid": "rgba(120, 130, 150, 0.18)",
}

# One colour per stock. A stock keeps the same colour on every chart.
STOCK_COLORS = [
    "#E07B00", "#0F9D75", "#B4478C", "#7A5BC7",
    "#C4452C", "#2E8B9A", "#8C6D1F", "#4B5D73",
]


def color_for(position):
    """Pick a colour by position, starting over when the list runs out."""
    return STOCK_COLORS[position % len(STOCK_COLORS)]


def style_figure(fig, title, y_title=None, height=420, unified_hover=True):
    """The shared look: title top left, legend top right, light grid, transparent background."""
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=18)),
        height=height,
        margin=dict(l=10, r=10, t=70, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis_title=y_title,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    if unified_hover:
        fig.update_layout(hovermode="x unified")  # one tooltip that shows every line for that date
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=COLORS["grid"], zeroline=False)
    return fig


# ======================================================================
# Portfolio vs benchmark
# ======================================================================

def growth_chart(portfolio_values, benchmark_values, benchmark_name, start_value):
    """The main chart: what the starting amount would have grown into."""
    fig = go.Figure()

    # The benchmark is added first so the portfolio can shade the gap between the two lines.
    fig.add_trace(go.Scatter(
        x=benchmark_values.index, y=benchmark_values, name=benchmark_name,
        line=dict(color=COLORS["benchmark"], width=2, dash="dot"),
        hovertemplate="%{y:$,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=portfolio_values.index, y=portfolio_values, name=PORTFOLIO_NAME,
        line=dict(color=COLORS["portfolio"], width=3),
        fill="tonexty", fillcolor="rgba(30, 79, 216, 0.10)",
        hovertemplate="%{y:$,.0f}<extra></extra>",
    ))

    fig = style_figure(fig, f"Growth of ${start_value:,.0f}", "Value")
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    return fig


def allocation_chart(weights):
    """Donut chart of the portfolio weights. Tickers with a 0% weight are left out."""
    labels = []
    values = []
    colors = []

    position = 0
    for ticker in weights:
        if weights[ticker] > 0:
            labels.append(ticker)
            values.append(round(weights[ticker] * 100, 1))
            colors.append(color_for(position))
        position = position + 1  # counts every ticker, so colours match the other charts

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.6, sort=False,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        textinfo="label+percent",
        hovertemplate="%{label}: %{value}%<extra></extra>",
    ))
    fig = style_figure(fig, "Allocation", height=420, unified_hover=False)
    fig.update_layout(showlegend=False)
    return fig


# ======================================================================
# Comparing stocks
# ======================================================================

def comparison_chart(rebased_stocks, rebased_benchmark, benchmark_name):
    """Every stock rebased to start at 100, so you can see who grew the most."""
    fig = go.Figure()

    position = 0
    for ticker in rebased_stocks.columns:
        fig.add_trace(go.Scatter(
            x=rebased_stocks.index, y=rebased_stocks[ticker], name=ticker,
            line=dict(color=color_for(position), width=2),
            hovertemplate="%{y:.1f}<extra></extra>",
        ))
        position = position + 1

    fig.add_trace(go.Scatter(
        x=rebased_benchmark.index, y=rebased_benchmark, name=benchmark_name,
        line=dict(color=COLORS["benchmark"], width=2, dash="dot"),
        hovertemplate="%{y:.1f}<extra></extra>",
    ))
    fig.add_hline(y=100, line_dash="dash", line_color=COLORS["grid"])

    return style_figure(fig, "Performance comparison (start = 100)", "Value, start = 100", height=450)


def risk_return_chart(stats_table, benchmark_name):
    """
    Each asset is one dot. Left is calmer, right is riskier. Higher is a better return.
    The best spot is the top left corner.
    """
    fig = go.Figure()

    position = 0
    for name in stats_table.index:
        x_value = stats_table.loc[name, VOLATILITY_COLUMN]
        y_value = stats_table.loc[name, RETURN_COLUMN]

        if name == PORTFOLIO_NAME:
            color, symbol, size = COLORS["portfolio"], "star", 20
        elif name == benchmark_name:
            color, symbol, size = COLORS["benchmark"], "diamond", 14
        else:
            color, symbol, size = color_for(position), "circle", 13
            position = position + 1

        fig.add_trace(go.Scatter(
            x=[x_value], y=[y_value], name=name, mode="markers+text",
            text=[name], textposition="top center",
            marker=dict(color=color, symbol=symbol, size=size),
            hovertemplate=name + "<br>Volatility: %{x:.1f}%<br>Annual return: %{y:.1f}%<extra></extra>",
            showlegend=False,
        ))

    fig = style_figure(fig, "Risk vs return", "Annual return (%)", height=450, unified_hover=False)
    fig.update_xaxes(title="Volatility (% per year), calmer is to the left")
    return fig


# ======================================================================
# Risk
# ======================================================================

def drawdown_chart(portfolio_drawdown, benchmark_drawdown, benchmark_name):
    """How far below the previous peak the value was on each day (the 'underwater' chart)."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=benchmark_drawdown.index, y=benchmark_drawdown * 100, name=benchmark_name,
        line=dict(color=COLORS["benchmark"], width=2, dash="dot"),
        hovertemplate="%{y:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=portfolio_drawdown.index, y=portfolio_drawdown * 100, name=PORTFOLIO_NAME,
        line=dict(color=COLORS["portfolio"], width=2),
        fill="tozeroy", fillcolor="rgba(30, 79, 216, 0.15)",
        hovertemplate="%{y:.1f}%<extra></extra>",
    ))

    fig = style_figure(fig, "Drawdown (drop from the previous peak)", "Drop from peak (%)", height=380)
    fig.update_yaxes(ticksuffix="%")
    return fig


def rolling_volatility_chart(portfolio_vol, benchmark_vol, benchmark_name):
    """Yearly-scaled volatility measured over a sliding window, to see risk rise and fall."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=benchmark_vol.index, y=benchmark_vol * 100, name=benchmark_name,
        line=dict(color=COLORS["benchmark"], width=2, dash="dot"),
        hovertemplate="%{y:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=portfolio_vol.index, y=portfolio_vol * 100, name=PORTFOLIO_NAME,
        line=dict(color=COLORS["portfolio"], width=2),
        hovertemplate="%{y:.1f}%<extra></extra>",
    ))

    fig = style_figure(fig, "Rolling volatility (30 trading days)", "Volatility (% per year)", height=380)
    fig.update_yaxes(ticksuffix="%")
    return fig


def correlation_chart(correlation):
    """
    Heatmap of how closely the daily returns move together.
    +1 (dark blue) = identical moves, 0 = unrelated, -1 (red) = opposite moves.
    Low numbers between your stocks mean better diversification.
    """
    names = list(correlation.columns)

    fig = go.Figure(go.Heatmap(
        z=correlation.values, x=names, y=names,
        zmin=-1, zmax=1, colorscale="RdBu",
        texttemplate="%{z:.2f}",
        hovertemplate="%{x} and %{y}: %{z:.2f}<extra></extra>",
        colorbar=dict(title="Correlation"),
    ))
    fig.update_yaxes(autorange="reversed")  # first ticker at the top, like a table

    height = max(380, 90 + 60 * len(names))
    return style_figure(fig, "Correlation of daily returns", height=height, unified_hover=False)


# ======================================================================
# Single stock view
# ======================================================================

def candlestick_chart(history, short_average, long_average, ticker, short_window, long_window):
    """
    Candlesticks (open, high, low, close) with two moving averages, plus trading volume.
    A green candle means the price closed higher than it opened that day.
    """
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.75, 0.25], vertical_spacing=0.03,
    )

    fig.add_trace(go.Candlestick(
        x=history.index,
        open=history["Open"], high=history["High"], low=history["Low"], close=history["Close"],
        name=ticker,
        increasing_line_color=COLORS["up"], decreasing_line_color=COLORS["down"],
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=short_average.index, y=short_average, name=f"{short_window}-day average",
        line=dict(color=STOCK_COLORS[0], width=1.5),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=long_average.index, y=long_average, name=f"{long_window}-day average",
        line=dict(color=STOCK_COLORS[3], width=1.5),
    ), row=1, col=1)

    # Volume bars: green on days the price went up, red on days it went down
    bar_colors = []
    for position in range(len(history)):
        if history["Close"].iloc[position] >= history["Open"].iloc[position]:
            bar_colors.append(COLORS["up"])
        else:
            bar_colors.append(COLORS["down"])

    fig.add_trace(go.Bar(
        x=history.index, y=history["Volume"], name="Volume",
        marker_color=bar_colors, showlegend=False,
    ), row=2, col=1)

    fig = style_figure(fig, f"{ticker} price", height=620)
    fig.update_layout(xaxis_rangeslider_visible=False)
    has_weekend_data = (history.index.dayofweek >= 5).any()  # crypto trades on weekends, stocks do not
    if not has_weekend_data:
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])  # hide the empty weekend gaps
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    return fig
