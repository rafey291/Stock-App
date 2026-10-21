import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

st.title("Stock Price Dashboard")

ticker_input = st.text_input("Enter a stock ticker", value="AAPL")
period = st.selectbox("Select time period", ["1mo", "3mo", "6mo", "1y", "2y"])

if ticker_input:
    data = yf.Ticker(ticker_input).history(period=period)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data["Close"], name="Close Price"))
    fig.update_layout(title=f"{ticker_input} Stock Price", xaxis_title="Date", yaxis_title="Price (USD)")
    
    st.plotly_chart(fig)
    st.dataframe(data.tail(10))

# ```
# streamlit run GraphApp.py:
# ```
