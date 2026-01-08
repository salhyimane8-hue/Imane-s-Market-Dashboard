import streamlit as st

# Page config
st.set_page_config(
    page_title="Financial Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns

# FRED API import
from fredapi import Fred



# Initialize FRED API (REPLACE WITH YOUR ACTUAL API KEY)
FRED_API_KEY = st.secrets.get("FRED_API_KEY", "your_fred_api_key_here")  # Get from: https://fred.stlouisfed.org/docs/api/api_key.html
fred = Fred(api_key=FRED_API_KEY)

# ====================== FRED Central Bank Data ======================
# FRED Central Bank Rate Series
CENTRAL_BANK_SERIES = {
    "Federal Reserve (FED) - Fedfund proxy": "FEDFUNDS",  # Effective Federal Funds Rate
    "European Central Bank (ECB)": "ECBDFR",  # ECB Deposit Facility Rate
    "Bank of England (BOE) - Sonia proxy": "IUDSOIA",  # SONIA Overnight Rate (proxy)
    "Bank of Japan (BOJ)": "IRSTCI01JPM156N",  # Japan Overnight Call Rate
    "Swiss National Bank (SNB)": "ECBMLFR",  # ECB Marginal Lending Facility Rate (proxy)
}

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_fred_data(series_id, start_date, end_date):
    """Fetch data from FRED API"""
    try:
        # Convert date strings if needed
        if isinstance(start_date, datetime.date):
            start_date = start_date.strftime("%Y-%m-%d")
        if isinstance(end_date, datetime.date):
            end_date = end_date.strftime("%Y-%m-%d")
        
        # Fetch data from FRED
        data = fred.get_series(series_id, start_date, end_date)
        
        if not data.empty:
            # Convert to Series if needed
            if isinstance(data, pd.DataFrame):
                data = data.iloc[:, 0]
            return data
    except Exception as e:
        st.warning(f"Error fetching {series_id}: {str(e)}")
    return None

def get_central_bank_data():
    """Fetch live central bank data from FRED"""
    central_bank_data = []
    
    for bank_name, series_id in CENTRAL_BANK_SERIES.items():
        try:
            # Get latest rate
            latest_data = fred.get_series(series_id, observation_start='2023-01-01')
            if not latest_data.empty:
                current_rate = latest_data.iloc[-1]
                
                # Get previous rate for change calculation
                if len(latest_data) > 1:
                    prev_rate = latest_data.iloc[-2]
                    last_change_pct = ((current_rate - prev_rate) / prev_rate * 100) if prev_rate != 0 else 0
                    last_change = f"{last_change_pct:+.2f}%" if last_change_pct != 0 else "No change"
                else:
                    last_change = "N/A"
                
                
                central_bank_data.append({
                    "Bank": bank_name,
                    "Current Rate": f"{current_rate:.2f}%" if current_rate else "N/A",
                    "FRED Series": series_id    # For charting
                })
            else:
                central_bank_data.append({
                    "Bank": bank_name,
                    "Current Rate": "N/A",
                    "FRED Series": series_id
                })
                
        except Exception as e:
            central_bank_data.append({
                "Bank": bank_name,
                "Current Rate": f"Error: {str(e)}",
                "FRED Series": series_id
            })
    
    return central_bank_data

# ====================== SESSION STATE INITIALIZATION ======================
if "page" not in st.session_state:
    st.session_state.page = "My Dashboard"

# For Market Indices
if "selected_index_tickers" not in st.session_state:
    st.session_state.selected_index_tickers = {}

# For Individual Equities
if "selected_equity_tickers" not in st.session_state:
    st.session_state.selected_equity_tickers = {}

# For Charts
if "chart_items" not in st.session_state:
    st.session_state.chart_items = []

# For FX
if "selected_fx_pairs" not in st.session_state:
    st.session_state.selected_fx_pairs = []
if "fx_base_currency" not in st.session_state:
    st.session_state.fx_base_currency = "EUR"
if "fx_unit_currency" not in st.session_state:
    st.session_state.fx_unit_currency = "USD"
if "fx_chart_items" not in st.session_state:
    st.session_state.fx_chart_items = []
if "show_correlation_matrix" not in st.session_state:
    st.session_state.show_correlation_matrix = False
if "fx_table_base_currency" not in st.session_state:
    st.session_state.fx_table_base_currency = "USD"
if "fx_quote_date" not in st.session_state:
    st.session_state.fx_quote_date = datetime.now().date()

# For Rates/Bonds charts
if "rates_chart_items" not in st.session_state:
    st.session_state.rates_chart_items = []

# For Commodities charts
if "commo_chart_items" not in st.session_state:
    st.session_state.commo_chart_items = []

# For current date selection (shared across pages)  ✅ Use DATE objects everywhere
if "selected_start" not in st.session_state:
    st.session_state.selected_start = (datetime.now() - timedelta(days=365)).date()
if "selected_end" not in st.session_state:
    st.session_state.selected_end = datetime.now().date()
if "ytd_start_date" not in st.session_state:
    st.session_state.ytd_start_date = datetime.now().replace(month=1, day=1).date()
if "decimals" not in st.session_state:
    st.session_state.decimals = 2

# For Chart settings ✅ Use DATE objects everywhere
if "chart_start_date" not in st.session_state:
    st.session_state.chart_start_date = (datetime.now() - timedelta(days=365)).date()
if "chart_end_date" not in st.session_state:
    st.session_state.chart_end_date = datetime.now().date()
if "use_log_scale" not in st.session_state:
    st.session_state.use_log_scale = False
if "normalize_data" not in st.session_state:
    st.session_state.normalize_data = True

# ====================== DATA DEFINITIONS ======================
EQUITY_INDICES = {
    "United States": {
        "S&P 500": "^GSPC",
        "NASDAQ Composite": "^IXIC",
        "Dow Jones Industrial": "^DJI",
        "Russell 2000": "^RUT",
        "S&P 400 MidCap": "^MID",
        "NYSE Composite": "^NYA",
        "Wilshire 5000": "^W5000",
        "S&P 100": "^OEX",
        "Dow Jones Transportation": "^DJT",
        "Dow Jones Utility": "^DJU"
    },
    "Europe": {
        "CAC 40 (France)": "^FCHI",
        "Euro Stoxx 50": "^STOXX50E",
        "DAX (Germany)": "^GDAXI",
        "FTSE 100 (UK)": "^FTSE",
        "IBEX 35 (Spain)": "^IBEX",
        "FTSE MIB (Italy)": "FTSEMIB.MI",
    },
    "Asia Pacific": {
        "Nikkei 225 (Japan)": "^N225",
        "Hang Seng (Hong Kong)": "^HSI",
        "Shanghai Composite (China)": "000001.SS",
        "TSEC (Taiwan)": "^TWII",
        "Nifty 50 (India)": "^NSEI",
    },
    "Emerging Markets": {
        "Bovespa (Brazil)": "^BVSP",
        "IPC (Mexico)": "^MXX",
    }
}

EQUITY_LISTS = {
    "S&P 500": [
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META", "BRK-B", "JPM", "V",
        "UNH", "XOM", "LLY", "JNJ", "WMT", "MA", "PG", "HD", "CVX", "MRK"
    ],
    "NASDAQ Composite": [
        "AMD", "INTC", "CSCO", "ADBE", "PYPL", "NFLX", "CMCSA", "PEP", "COST", "AVGO",
        "QCOM", "TXN", "AMGN", "INTU", "ISRG"
    ],
    "Dow Jones Industrial": ["AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "DOW", "GS", "HON"],
    "CAC 40 (France)": ["MC.PA", "AIR.PA", "SAN.PA", "OR.PA", "AI.PA", "BNP.PA", "CAP.PA", "RI.PA", "SAF.PA", "DG.PA"],
    "DAX (Germany)": ["SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "BMW.DE", "BAYN.DE", "DBK.DE", "VOW3.DE", "MUV2.DE", "ADS.DE"],
    "FTSE 100 (UK)": ["HSBA.L", "BP.L", "GSK.L", "RIO.L", "ULVR.L", "AZN.L", "BATS.L", "DGE.L", "VOD.L", "NG.L"],
    "Nikkei 225 (Japan)": ["7203.T", "9984.T", "6758.T", "6861.T", "8306.T", "9432.T", "9433.T", "9437.T", "9983.T", "8766.T"],
    "Hang Seng (Hong Kong)": ["0700.HK", "0939.HK", "1398.HK", "0388.HK", "0005.HK", "1299.HK", "2318.HK", "3988.HK", "2628.HK", "0941.HK"],
    "Nifty 50 (India)": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS"],
    "Bovespa (Brazil)": ["PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "ABEV3.SA", "WEGE3.SA", "BBAS3.SA", "B3SA3.SA", "RENT3.SA", "SUZB3.SA"],
    "IPC (Mexico)": ["WALMEX.MX", "AMXL.MX", "FEMSAUBD.MX", "GMEXICOB.MX", "GFNORTEO.MX"],
    "Euro Stoxx 50": ["ASML.AS", "LIN.DE", "SAN.PA", "SAP.DE", "AIR.PA", "MC.PA", "OR.PA", "SIEGY", "ALV.DE", "AI.PA"],
}

FX_CURRENCIES = {
    "G10 Currencies": {
        "EUR": "EUR",
        "JPY": "JPY",
        "GBP": "GBP",
        "CHF": "CHF",
        "CAD": "CAD",
        "AUD": "AUD",
        "NZD": "NZD",
        "NOK": "NOK",
        "SEK": "SEK",
        "DKK": "DKK",
        "USD": "USD",
    },
    "Emerging Currencies": {
        "CNY": "CNY",
        "INR": "INR",
        "BRL": "BRL",
        "MXN": "MXN",
        "ZAR": "ZAR",
        "TRY": "TRY",
        "RUB": "RUB",
        "KRW": "KRW",
        "SGD": "SGD",
        "HKD": "HKD",
    },
    "Major Crosses": {
        "EUR/GBP": "EURGBP=X",
        "EUR/JPY": "EURJPY=X",
        "GBP/JPY": "GBPJPY=X",
        "EUR/CHF": "EURCHF=X",
        "AUD/CAD": "AUDCAD=X",
        "EUR/AUD": "EURAUD=X",
        "GBP/AUD": "GBPAUD=X",
    }
}

# ====================== HELPER FUNCTIONS ======================
@st.cache_data(ttl=86400)
def get_company_name(ticker):
    """Get company name from ticker"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return info.get("longName", info.get("shortName", ticker))
    except:
        return ticker

@st.cache_data(ttl=600)
def get_equity_data(ticker, start_date, end_date, ytd_start_date):
    """Fetch and calculate data for an equity"""
    try:
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        ytd_start_str = ytd_start_date.strftime("%Y-%m-%d")

        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_str, end=end_str)

            if hist.empty or len(hist) < 2:
                return None

            current_value = hist["Close"].iloc[-1]
            prev_value = hist["Close"].iloc[-2] if len(hist) > 1 else current_value

            daily_change_pct = ((current_value - prev_value) / prev_value * 100) if prev_value > 0 else 0

            if len(hist) >= 6:
                week_ago_value = hist["Close"].iloc[-6]
                week_change_pct = ((current_value - week_ago_value) / week_ago_value * 100) if week_ago_value > 0 else 0
            else:
                week_change_pct = np.nan

            try:
                ytd_data = stock.history(start=ytd_start_str, end=end_str)
                if not ytd_data.empty and len(ytd_data) > 1:
                    ytd_start_value = ytd_data["Close"].iloc[0]
                    ytd_change_pct = ((current_value - ytd_start_value) / ytd_start_value * 100) if ytd_start_value > 0 else np.nan
                else:
                    ytd_change_pct = np.nan
            except:
                ytd_change_pct = np.nan

            return {"Value": current_value, "Daily %": daily_change_pct, "1 Week %": week_change_pct, "YTD %": ytd_change_pct}

        except Exception:
            try:
                data = yf.download(ticker, start=start_str, end=end_str, progress=False)
                if not data.empty and len(data) >= 2:
                    current_value = data["Close"].iloc[-1]
                    prev_value = data["Close"].iloc[-2] if len(data) > 1 else current_value

                    daily_change_pct = ((current_value - prev_value) / prev_value * 100) if prev_value > 0 else 0

                    if len(data) >= 6:
                        week_ago_value = data["Close"].iloc[-6]
                        week_change_pct = ((current_value - week_ago_value) / week_ago_value * 100) if week_ago_value > 0 else 0
                    else:
                        week_change_pct = np.nan

                    return {"Value": current_value, "Daily %": daily_change_pct, "1 Week %": week_change_pct, "YTD %": np.nan}
            except:
                pass

            return None

    except:
        return None

@st.cache_data(ttl=600)
def get_historical_data(ticker, start_date, end_date):
    """Get historical price data for charting - returns clean Series"""
    try:
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        data = yf.download(ticker, start=start_str, end=end_str, progress=False, auto_adjust=True)

        if not data.empty:
            if "Close" in data.columns:
                close_prices = data["Close"]
            elif "Adj Close" in data.columns:
                close_prices = data["Adj Close"]
            else:
                close_prices = data.iloc[:, 0]

            if isinstance(close_prices, pd.DataFrame):
                close_prices = close_prices.iloc[:, 0]

            return close_prices

        return None
    except:
        return None

@st.cache_data(ttl=600)
def get_fx_data(base_currency, unit_currency, start_date, end_date):
    """Get FX pair data - returns clean Series"""
    try:
        if base_currency == "USD":
            ticker = f"{unit_currency}=X"       # e.g. JPY=X means USD/JPY
        elif unit_currency == "USD":
            ticker = f"{base_currency}{unit_currency}=X"  # e.g. EURUSD=X
        else:
            ticker = f"{base_currency}{unit_currency}=X"

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        data = yf.download(ticker, start=start_str, end=end_str, progress=False)
        if not data.empty:
            close_prices = data["Close"] if "Close" in data.columns else data.iloc[:, 0]
            if isinstance(close_prices, pd.DataFrame):
                close_prices = close_prices.iloc[:, 0]
            return close_prices
    except:
        return None
    return None

@st.cache_data(ttl=600)
def get_fx_rate_single_date(base_currency, unit_currency, date):
    """Get FX rate for a specific date"""
    try:
        start_date = date - timedelta(days=7)
        end_date = date + timedelta(days=1)

        data = get_fx_data(base_currency, unit_currency, start_date, end_date)
        if data is not None and not data.empty:
            if pd.Timestamp(date) in data.index:
                return float(data.loc[pd.Timestamp(date)])
            else:
                available_dates = data.index[data.index <= pd.Timestamp(date)]
                if len(available_dates) > 0:
                    closest_date = available_dates[-1]
                    return float(data.loc[closest_date])
    except:
        pass
    return None

def add_to_selection(selection_dict, region, index, tickers, display_name_func=None):
    if region not in selection_dict:
        selection_dict[region] = {}
    if index not in selection_dict[region]:
        selection_dict[region][index] = []

    for ticker in tickers:
        if display_name_func:
            item = {"ticker": ticker, "display_name": display_name_func(ticker)}
        else:
            item = {"ticker": ticker, "display_name": ticker}

        if item not in selection_dict[region][index]:
            selection_dict[region][index].append(item)

def remove_from_selection(selection_dict, region, index, tickers):
    if region in selection_dict and index in selection_dict[region]:
        items_to_keep = [item for item in selection_dict[region][index] if item["ticker"] not in tickers]
        selection_dict[region][index] = items_to_keep

        if not selection_dict[region][index]:
            del selection_dict[region][index]
        if not selection_dict[region]:
            del selection_dict[region]

def get_all_selected_items(selection_dict):
    all_items = []
    for region, indexes in selection_dict.items():
        for index, items in indexes.items():
            for item in items:
                all_items.append({
                    "region": region,
                    "index": index,
                    "ticker": item["ticker"],
                    "display_name": item["display_name"]
                })
    return all_items

def format_value(val, decimals=2):
    """General formatter used elsewhere (kept)."""
    if isinstance(val, (int, float)) and not pd.isna(val):
        if abs(val) >= 1_000_000:
            return f"{val/1_000_000:.{decimals}f}M"
        elif abs(val) >= 1_000:
            return f"{val/1_000:.{decimals}f}K"
        else:
            return f"{val:,.{decimals}f}"
    elif pd.isna(val):
        return "N/A"
    return str(val)

def format_nominal(val, decimals=2):
    """Nominal formatter (no K/M)."""
    if isinstance(val, (int, float)) and not pd.isna(val):
        return f"{val:,.{decimals}f}"
    return "N/A"

def format_percentage(val):
    if isinstance(val, (int, float)) and not pd.isna(val):
        return f"{val:.2f}%"
    elif isinstance(val, str) and val == "N/A":
        return "N/A"
    return ""

def initialize_selections():
    if not st.session_state.selected_index_tickers:
        for region, indices in EQUITY_INDICES.items():
            for index_name, ticker in indices.items():
                add_to_selection(
                    st.session_state.selected_index_tickers,
                    region,
                    index_name,
                    [ticker],
                    lambda x, _name=index_name: _name
                )

# ====================== SIDEBAR - NAVIGATION & CONTROLS ======================
with st.sidebar:
    st.title("🌐 Financial Dashboard")

    st.markdown("### 📊 Navigation")
    page_options = ["My Dashboard", "Equity", "FX", "Rates/Bonds", "Commodities"]
    selected_page = st.selectbox("Select Page", page_options, key="page_select", label_visibility="collapsed")

    if selected_page != st.session_state.page:
        st.session_state.page = selected_page
        st.rerun()

    st.markdown("---")
    st.header("📅 Global Date Range")

    selected_start = st.date_input("Start Date", value=st.session_state.selected_start)
    selected_end = st.date_input("End Date", value=st.session_state.selected_end)

    st.session_state.selected_start = selected_start
    st.session_state.selected_end = selected_end

    ytd_start_date = datetime(selected_end.year, 1, 1).date()
    st.session_state.ytd_start_date = ytd_start_date

    st.markdown("---")
    st.header("⚙️ Display Options")

    decimals = st.slider("Decimal Places", 0, 4, st.session_state.decimals)
    st.session_state.decimals = decimals

    if st.button("🔄 Refresh All Data", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.info(f"**Selected Range:** {selected_start} to {selected_end}")
    st.info(f"**YTD Range:** {ytd_start_date} to {selected_end}")

# ====================== PAGE 1: MY DASHBOARD ======================
def render_my_dashboard():
    st.title("📊 My Dashboard")
    st.markdown("### Personal Overview of Key Financial Metrics")

    initialize_selections()

    def color_percentage(val):
        if isinstance(val, str) and "%" in val:
            try:
                num = float(val.replace("%", ""))
                color = "#10B981" if num > 0 else "#EF4444" if num < 0 else "#6B7280"
                return f"color: {color}; font-weight: bold;"
            except:
                return ""
        return ""

    tab1, tab2, tab3 = st.tabs(["📈 Market Overview", "🏛️ Central Banks", "📊 Economic Data"])

    with tab1:
     col1, col2 = st.columns(2)

    with col1:
        st.subheader("Equity Markets")
        major_indices = {
            "S&P 500": "^GSPC",
            "NASDAQ": "^IXIC",
            "Dow Jones": "^DJI",
            "Euro Stoxx 50": "^STOXX50E",
            "DAX": "^GDAXI",
            "FTSE 100": "^FTSE",
            "Nikkei 225": "^N225",
            "Hang Seng": "^HSI"
        }

        equity_data = []
        for name, ticker in major_indices.items():
            result = get_equity_data(ticker, selected_start, selected_end, ytd_start_date)
            if result:
                equity_data.append({"Index": name, "Value": result["Value"], "1D %": result["Daily %"], "YTD %": result["YTD %"]})

        if equity_data:
            df_equity = pd.DataFrame(equity_data)
            df_display = df_equity.copy()
            df_display["Value"] = df_display["Value"].apply(lambda x: format_value(x, decimals))
            df_display["1D %"] = df_display["1D %"].apply(format_percentage)
            df_display["YTD %"] = df_display["YTD %"].apply(format_percentage)

            styled = df_display.style.map(color_percentage, subset=["1D %", "YTD %"])
            st.dataframe(styled, use_container_width=True, hide_index=True)

    with col2:
        st.subheader("FX Markets")
        fx_pairs = {
            "EUR/USD": "EURUSD=X",
            "GBP/USD": "GBPUSD=X",
            "USD/JPY": "JPY=X",
            "USD/CHF": "CHF=X",
            "AUD/USD": "AUDUSD=X",
            "USD/CAD": "CAD=X"
        }

        fx_data = []
        for pair, ticker in fx_pairs.items():
            result = get_equity_data(ticker, selected_start, selected_end, ytd_start_date)
            if result:
                fx_data.append({"Pair": pair, "Rate": result["Value"], "1D %": result["Daily %"], "YTD %": result["YTD %"]})

        if fx_data:
            df_fx = pd.DataFrame(fx_data)
            df_display = df_fx.copy()
            df_display["Rate"] = df_display["Rate"].apply(lambda x: format_value(x, decimals))
            df_display["1D %"] = df_display["1D %"].apply(format_percentage)
            df_display["YTD %"] = df_display["YTD %"].apply(format_percentage)

            styled = df_display.style.map(color_percentage, subset=["1D %", "YTD %"])
            st.dataframe(styled, use_container_width=True, hide_index=True)

    # ====== KEY INDICATORS EN PLEINE LARGEUR (APRÈS LES DEUX COLONNES) ======
    st.markdown("---")
    st.subheader("Key Indicators")
    
    indicators = {"VIX": "^VIX", "DXY": "DX-Y.NYB", "Gold": "GC=F", "Oil (WTI)": "CL=F"}
    
    # Créer 2 colonnes pour les indicateurs
    ind_col1, ind_col2 = st.columns(2)
    
    ind_data = []
    for name, ticker in indicators.items():
        result = get_equity_data(ticker, selected_start, selected_end, ytd_start_date)
        if result:
            ind_data.append({"Indicator": name, "Value": result["Value"], "1D %": result["Daily %"], "YTD %": result["YTD %"]})
    
    if ind_data:
        df_ind = pd.DataFrame(ind_data)
        df_display = df_ind.copy()
        df_display["Value"] = df_display["Value"].apply(lambda x: format_value(x, decimals))
        df_display["1D %"] = df_display["1D %"].apply(format_percentage)
        df_display["YTD %"] = df_display["YTD %"].apply(format_percentage)
        
        # Afficher dans une seule dataframe en pleine largeur
        styled = df_display.style.map(color_percentage, subset=["1D %", "YTD %"])
        st.dataframe(styled, use_container_width=True, hide_index=True)


    with tab2:
     st.subheader("Central Bank Rates & Policies (Live FRED Data)")
    
    # Check if FRED API key is set
    if FRED_API_KEY == "your_fred_api_key_here":
        st.error("⚠️ FRED API Key not configured!")
        st.info("Please get a free API key from: https://fred.stlouisfed.org/docs/api/api_key.html")
        st.info("Then replace 'your_fred_api_key_here' with your actual API key in line 15 of the code.")
        st.warning("No data available - FRED API key required.")
    else:
        # Fetch live central bank data from FRED
        try:
            central_banks = get_central_bank_data()
            
            if not central_banks:
                st.warning("No central bank data available from FRED API.")
                return
            
            # Display table (without FRED Series column for cleaner view)
            display_df = pd.DataFrame(central_banks)
            # Remove the technical 'FRED Series' column from display
            if 'FRED Series' in display_df.columns:
                display_df = display_df.drop(columns=['FRED Series'])
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Add download button for central bank data
            st.markdown("---")
            if st.button("📥 Download Central Bank Data", use_container_width=True):
                download_df = pd.DataFrame(central_banks)
                csv = download_df.to_csv(index=False)
                st.download_button(
                    label="Confirm Download",
                    data=csv,
                    file_name=f"central_bank_rates_{datetime.now().date()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                     
        except Exception as e:
            st.error(f"Error fetching FRED data: {str(e)}")
            st.info("Please check your FRED API key and internet connection.")
            
    with tab3:
        st.subheader("Economic Indicators")
        economic_data = [
            {"Country": "United States", "GDP QoQ": "4.9%", "Inflation": "3.2%", "Core Inflation": "4.0%", "Unemployment": "3.9%", "PMI": "50.0", "Last Update": "Nov 2023"},
            {"Country": "Eurozone", "GDP QoQ": "0.1%", "Inflation": "2.9%", "Core Inflation": "4.2%", "Unemployment": "6.5%", "PMI": "43.1", "Last Update": "Nov 2023"},
            {"Country": "United Kingdom", "GDP QoQ": "0.0%", "Inflation": "4.6%", "Core Inflation": "5.7%", "Unemployment": "4.2%", "PMI": "44.8", "Last Update": "Nov 2023"},
            {"Country": "Japan", "GDP QoQ": "-0.5%", "Inflation": "3.3%", "Core Inflation": "2.9%", "Unemployment": "2.6%", "PMI": "48.1", "Last Update": "Nov 2023"},
            {"Country": "China", "GDP QoQ": "1.3%", "Inflation": "-0.2%", "Core Inflation": "0.6%", "Unemployment": "5.0%", "PMI": "49.4", "Last Update": "Nov 2023"},
        ]
        st.dataframe(pd.DataFrame(economic_data), use_container_width=True, hide_index=True)

# ====================== PAGE 2: EQUITY ======================
def render_equity_page():
    st.title("📈 Equity Markets Dashboard")
    st.markdown("Real-time equity data across global markets")

    initialize_selections()

    with st.sidebar:
        st.markdown("---")
        st.header("📊 Market Indices Filters")

        if st.button("✅ Select All Indices", use_container_width=True, key="select_all_idx_btn"):
            st.session_state.selected_index_tickers = {}
            for region, indices in EQUITY_INDICES.items():
                for index_name, ticker in indices.items():
                    add_to_selection(st.session_state.selected_index_tickers, region, index_name, [ticker], lambda x, _name=index_name: _name)
            st.rerun()

        regions = list(EQUITY_INDICES.keys())
        selected_regions_idx = st.multiselect("Select Region(s) for Indices:", options=regions, default=regions, key="idx_region_multiselect")

        available_indices_idx = []
        idx_ticker_map = {}
        if selected_regions_idx:
            for region in selected_regions_idx:
                if region in EQUITY_INDICES:
                    for idx in EQUITY_INDICES[region].keys():
                        ticker = EQUITY_INDICES[region][idx]
                        display_text = f"{region}: {idx}"
                        available_indices_idx.append(display_text)
                        idx_ticker_map[display_text] = {"region": region, "index": idx, "ticker": ticker, "display_name": idx}

        selected_indices_full = st.multiselect("Select Index(es):", options=available_indices_idx, default=available_indices_idx, key="idx_index_multiselect")

        col_add, col_remove = st.columns(2)
        with col_add:
            if st.button("➕ Add Selected Indices", use_container_width=True, key="idx_add_btn"):
                for display_text in selected_indices_full:
                    if display_text in idx_ticker_map:
                        data = idx_ticker_map[display_text]
                        add_to_selection(st.session_state.selected_index_tickers, data["region"], data["index"], [data["ticker"]], lambda x, _name=data["display_name"]: _name)
                st.rerun()

        with col_remove:
            if st.button("🗑️ Clear Indices", use_container_width=True, key="idx_clear_btn"):
                st.session_state.selected_index_tickers = {}
                st.rerun()

        st.markdown("---")
        st.header("🏢 Individual Equities Filters")

        if st.button("✅ Select All Equities from Indices", use_container_width=True, key="select_all_eq_btn"):
            st.session_state.selected_equity_tickers = {}
            for display_text in selected_indices_full:
                if display_text in idx_ticker_map:
                    data = idx_ticker_map[display_text]
                    index_name = data["index"]
                    if index_name in EQUITY_LISTS:
                        for ticker in EQUITY_LISTS[index_name]:
                            add_to_selection(st.session_state.selected_equity_tickers, data["region"], index_name, [ticker], get_company_name)
            st.rerun()

        all_equities_options = []
        equity_ticker_map = {}
        if selected_indices_full:
            for selection in selected_indices_full:
                if ": " in selection:
                    region, index_name = selection.split(": ", 1)
                    if index_name in EQUITY_LISTS:
                        for ticker in EQUITY_LISTS[index_name]:
                            company_name = get_company_name(ticker)
                            display_text = f"{region}: {index_name} - {ticker} - {company_name}"
                            all_equities_options.append(display_text)
                            equity_ticker_map[display_text] = {"region": region, "index": index_name, "ticker": ticker}

        selected_equities_display = st.multiselect(
            "Select Equities:",
            options=all_equities_options,
            default=all_equities_options[: min(10, len(all_equities_options))],
            placeholder="Choose equities...",
            key="eq_equity_multiselect"
        )

        col_add_eq, col_remove_eq = st.columns(2)
        with col_add_eq:
            if st.button("➕ Add Selected Equities", use_container_width=True, key="eq_add_btn"):
                for display_text in selected_equities_display:
                    if display_text in equity_ticker_map:
                        data = equity_ticker_map[display_text]
                        add_to_selection(st.session_state.selected_equity_tickers, data["region"], data["index"], [data["ticker"]], get_company_name)
                st.rerun()

        with col_remove_eq:
            if st.button("🗑️ Clear Equities", use_container_width=True, key="eq_clear_btn"):
                st.session_state.selected_equity_tickers = {}
                st.rerun()

        st.markdown("---")
        st.header("📈 Chart Configuration")

        st.subheader("Chart Date Range")
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            chart_start = st.date_input("Start Date", value=st.session_state.chart_start_date, key="chart_start_input")
            st.session_state.chart_start_date = chart_start
        with chart_col2:
            chart_end = st.date_input("End Date", value=st.session_state.chart_end_date, key="chart_end_input")
            st.session_state.chart_end_date = chart_end

        st.subheader("Chart Options")
        col_log, col_norm = st.columns(2)
        with col_log:
            st.session_state.use_log_scale = st.checkbox("Log Scale", value=st.session_state.use_log_scale, key="log_scale_check")
        with col_norm:
            st.session_state.normalize_data = st.checkbox("Normalize to 100", value=st.session_state.normalize_data, key="normalize_check")

        st.subheader("Add Assets to Chart")

        chart_assets = []
        for region, indices in EQUITY_INDICES.items():
            for index_name, ticker in indices.items():
                chart_assets.append({"type": "Index", "region": region, "name": index_name, "ticker": ticker, "display": f"📊 {index_name} ({region})"})

        for index_name, equities in EQUITY_LISTS.items():
            for ticker in equities:
                company_name = get_company_name(ticker)
                region = "Unknown"
                for reg, idxs in EQUITY_INDICES.items():
                    if index_name in idxs:
                        region = reg
                        break
                chart_assets.append({"type": "Equity", "region": region, "name": company_name, "ticker": ticker, "display": f"🏢 {company_name} ({ticker})"})

        fx_pairs = {"EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "JPY=X", "USD/CHF": "CHF=X", "AUD/USD": "AUDUSD=X", "USD/CAD": "CAD=X"}
        for pair, ticker in fx_pairs.items():
            chart_assets.append({"type": "FX", "region": "Forex", "name": pair, "ticker": ticker, "display": f"💱 {pair}"})

        indicators = {"VIX": "^VIX", "DXY": "DX-Y.NYB", "Gold": "GC=F", "Oil (WTI)": "CL=F"}
        for name, ticker in indicators.items():
            chart_assets.append({"type": "Indicator", "region": "US", "name": name, "ticker": ticker, "display": f"📈 {name}"})

        chart_options = [asset["display"] for asset in chart_assets]
        chart_asset_map = {asset["display"]: asset for asset in chart_assets}

        selected_chart_assets = st.multiselect("Select Assets to Chart:", options=chart_options, default=[], placeholder="Choose assets...", key="chart_asset_select")

        col_add_chart, col_clear_chart = st.columns(2)
        with col_add_chart:
            if st.button("➕ Add to Chart", use_container_width=True, key="add_chart_btn"):
                for display_text in selected_chart_assets:
                    if display_text in chart_asset_map:
                        asset = chart_asset_map[display_text]
                        if not any(item["ticker"] == asset["ticker"] for item in st.session_state.chart_items):
                            st.session_state.chart_items.append({
                                "type": asset["type"],
                                "region": asset["region"],
                                "name": asset["name"],
                                "ticker": asset["ticker"],
                                "display": asset["display"],
                                "color": None
                            })
                st.rerun()
        with col_clear_chart:
            if st.button("🗑️ Clear Chart", use_container_width=True, key="clear_chart_btn"):
                st.session_state.chart_items = []
                st.rerun()

    tab1, tab2, tab3 = st.tabs(["📊 Market Indices", "🏢 Individual Equities", "📈 Interactive Charts"])

    with tab1:
        st.header("Market Indices")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"Date Range: {selected_start} to {selected_end}")
            st.caption(f"📅 YTD Period: {ytd_start_date} to {selected_end}")
        with col2:
            st.button("📥 Download Data", use_container_width=True, key="idx_download_btn")

        st.markdown("---")

        all_selected_indices = get_all_selected_items(st.session_state.selected_index_tickers)

        if all_selected_indices:
            with st.expander("📋 Selected Indices", expanded=False):
                indices_by_region = {}
                for idx in all_selected_indices:
                    indices_by_region.setdefault(idx["region"], []).append(idx)
                for region, indices in indices_by_region.items():
                    st.write(f"**{region}**")
                    st.write(", ".join([f"{idx['display_name']}" for idx in indices]))

            all_data = []
            for region, indices in indices_by_region.items():
                all_data.append({"Index": f"📍 {region}", "Value": "", "Daily %": "", "1 Week %": "", "YTD %": ""})
                for idx in indices:
                    result = get_equity_data(idx["ticker"], selected_start, selected_end, ytd_start_date)
                    if result:
                        all_data.append({"Index": f"  • {idx['display_name']}", "Value": result["Value"], "Daily %": result["Daily %"], "1 Week %": result["1 Week %"], "YTD %": result["YTD %"]})
                    else:
                        all_data.append({"Index": f"  • {idx['display_name']}", "Value": "N/A", "Daily %": "N/A", "1 Week %": "N/A", "YTD %": "N/A"})
                if list(indices_by_region.keys()).index(region) < len(indices_by_region) - 1:
                    all_data.append({"Index": "", "Value": "", "Daily %": "", "1 Week %": "", "YTD %": ""})

            df_combined = pd.DataFrame(all_data)

            df_display = df_combined.copy()
            df_display["Value"] = df_display["Value"].apply(lambda x: format_value(x, decimals))
            for col in ["Daily %", "1 Week %", "YTD %"]:
                df_display[col] = df_display[col].apply(format_percentage)

            def color_pct(val):
                if isinstance(val, str) and "%" in val and val.strip() and val != "N/A":
                    try:
                        num_val = float(val.replace("%", "").strip())
                        if num_val > 0:
                            return "color: #10B981; font-weight: bold;"
                        elif num_val < 0:
                            return "color: #EF4444; font-weight: bold;"
                        else:
                            return "color: #6B7280;"
                    except:
                        return ""
                return ""

            def style_index(val):
                if isinstance(val, str) and "📍" in val:
                    return "font-weight: bold; color: #1E3A8A; font-size: 1.1em; background-color: #F0F2F6;"
                elif isinstance(val, str) and "•" in val:
                    return "padding-left: 20px;"
                return ""

            styled_df = (
                df_display.style
                .map(color_pct, subset=["Daily %", "1 Week %", "YTD %"])
                .map(style_index, subset=["Index"])
                .set_properties(subset=["Value", "Daily %", "1 Week %", "YTD %"], **{"text-align": "right", "padding-right": "15px"})
            )

            table_height = min(800, max(150, 100 + (len(df_display) * 38)))
            st.dataframe(styled_df, use_container_width=True, height=table_height, hide_index=True)

            st.markdown("---")
            download_data = []
            for _, row in df_combined.iterrows():
                if "•" in str(row["Index"]):
                    index_name = str(row["Index"]).replace("•", "").strip()
                    download_data.append({
                        "Index": index_name,
                        "Value": row["Value"] if isinstance(row["Value"], (int, float)) else "",
                        "Daily %": row["Daily %"] if isinstance(row["Daily %"], (int, float)) else "",
                        "1 Week %": row["1 Week %"] if isinstance(row["1 Week %"], (int, float)) else "",
                        "YTD %": row["YTD %"] if isinstance(row["YTD %"], (int, float)) and not pd.isna(row["YTD %"]) else ""
                    })
            if download_data:
                st.download_button(
                    label="📥 Download Index Data",
                    data=pd.DataFrame(download_data).to_csv(index=False),
                    file_name=f"indices_data_{selected_start}_{selected_end}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.info("💡 Use the sidebar filters to select indices from different regions.")

    with tab2:
        st.header("Individual Equities")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"Date Range: {selected_start} to {selected_end}")
            st.caption(f"📅 YTD Period: {ytd_start_date} to {selected_end}")
        with col2:
            st.button("📥 Download Data", use_container_width=True, key="eq_download_btn")

        st.markdown("---")

        all_selected_equities = get_all_selected_items(st.session_state.selected_equity_tickers)

        if all_selected_equities:
            with st.expander("📋 Selected Equities", expanded=False):
                equities_by_region_index = {}
                for equity in all_selected_equities:
                    equities_by_region_index.setdefault(equity["region"], {}).setdefault(equity["index"], []).append(equity)
                for region, indexes in equities_by_region_index.items():
                    st.write(f"**{region}**")
                    for index, equities in indexes.items():
                        st.write(f"  *{index}*: {len(equities)} equities")

            equity_data = []
            for region, indexes in equities_by_region_index.items():
                equity_data.append({"Equity": f"📍 {region}", "Value": "", "Daily %": "", "1 Week %": "", "YTD %": ""})
                for index, equities in indexes.items():
                    equity_data.append({"Equity": f"  📊 {index}", "Value": "", "Daily %": "", "1 Week %": "", "YTD %": ""})
                    for equity in equities:
                        result = get_equity_data(equity["ticker"], selected_start, selected_end, ytd_start_date)
                        if result:
                            equity_data.append({"Equity": f"    • {equity['display_name']}", "Value": result["Value"], "Daily %": result["Daily %"], "1 Week %": result["1 Week %"], "YTD %": result["YTD %"]})
                        else:
                            equity_data.append({"Equity": f"    • {equity['display_name']}", "Value": "N/A", "Daily %": "N/A", "1 Week %": "N/A", "YTD %": "N/A"})
                if list(equities_by_region_index.keys()).index(region) < len(equities_by_region_index) - 1:
                    equity_data.append({"Equity": "", "Value": "", "Daily %": "", "1 Week %": "", "YTD %": ""})

            df_equities = pd.DataFrame(equity_data)
            df_display = df_equities.copy()
            df_display["Value"] = df_display["Value"].apply(lambda x: format_value(x, decimals))
            for col in ["Daily %", "1 Week %", "YTD %"]:
                df_display[col] = df_display[col].apply(format_percentage)

            def style_equity(val):
                if isinstance(val, str) and "📍" in val:
                    return "font-weight: bold; color: #1E3A8A; font-size: 1.1em; background-color: #F0F2F6;"
                elif isinstance(val, str) and "📊" in val:
                    return "font-weight: bold; color: #4B5563; background-color: #F3F4F6; padding-left: 20px;"
                elif isinstance(val, str) and "•" in val:
                    return "padding-left: 40px;"
                return ""

            styled_df = (
                df_display.style
                .map(color_pct, subset=["Daily %", "1 Week %", "YTD %"])
                .map(style_equity, subset=["Equity"])
                .set_properties(subset=["Value", "Daily %", "1 Week %", "YTD %"], **{"text-align": "right", "padding-right": "15px"})
            )

            table_height = min(800, max(150, 100 + (len(df_display) * 38)))
            st.dataframe(styled_df, use_container_width=True, height=table_height, hide_index=True)

            st.markdown("---")
            download_data = []
            for _, row in df_equities.iterrows():
                if "•" in str(row["Equity"]):
                    equity_name = str(row["Equity"]).replace("•", "").strip()
                    download_data.append({
                        "Equity": equity_name,
                        "Value": row["Value"] if isinstance(row["Value"], (int, float)) else "",
                        "Daily %": row["Daily %"] if isinstance(row["Daily %"], (int, float)) else "",
                        "1 Week %": row["1 Week %"] if isinstance(row["1 Week %"], (int, float)) else "",
                        "YTD %": row["YTD %"] if isinstance(row["YTD %"], (int, float)) and not pd.isna(row["YTD %"]) else ""
                    })
            if download_data:
                st.download_button(
                    label="📥 Download Equity Data",
                    data=pd.DataFrame(download_data).to_csv(index=False),
                    file_name=f"equities_{selected_start}_{selected_end}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.info("💡 Use the sidebar filters to select equities from different regions and indexes.")

    with tab3:
        st.header("📈 Interactive Charts")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"Chart Period: {st.session_state.chart_start_date} to {st.session_state.chart_end_date}")
        with col2:
            col_log_display, col_norm_display = st.columns(2)
            with col_log_display:
                st.metric("Log Scale", "On" if st.session_state.use_log_scale else "Off")
            with col_norm_display:
                st.metric("Normalized", "Yes" if st.session_state.normalize_data else "No")

        st.markdown("---")

        if st.session_state.chart_items:
            with st.expander("📋 Assets in Chart", expanded=True):
                cols = st.columns(3)
                for i, item in enumerate(list(st.session_state.chart_items)):
                    with cols[i % 3]:
                        container = st.container(border=True)
                        container.write(f"**{item['display']}**")
                        if container.button("❌ Remove", key=f"remove_chart_{item['ticker']}"):
                            st.session_state.chart_items.remove(item)
                            st.rerun()

            all_data = {}
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, item in enumerate(st.session_state.chart_items):
                status_text.text(f"Fetching data for {item['name']}...")
                data = get_historical_data(item["ticker"], st.session_state.chart_start_date, st.session_state.chart_end_date)
                if data is not None and not data.empty:
                    if isinstance(data, pd.DataFrame):
                        data = data.iloc[:, 0]
                    all_data[item["ticker"]] = {"data": data, "name": item["name"], "display": item["display"], "type": item["type"]}
                progress_bar.progress((i + 1) / len(st.session_state.chart_items))

            progress_bar.empty()
            status_text.empty()

            if all_data:
                fig = go.Figure()
                colors = px.colors.qualitative.Set1 + px.colors.qualitative.Set2 + px.colors.qualitative.Set3

                for i, (ticker, item_data) in enumerate(all_data.items()):
                    price_data = item_data["data"]
                    if isinstance(price_data, pd.DataFrame):
                        price_data = price_data.iloc[:, 0]

                    if st.session_state.normalize_data and not price_data.empty:
                        first_value = float(price_data.iloc[0])
                        if first_value > 0:
                            price_data = (price_data / first_value) * 100

                    fig.add_trace(go.Scatter(
                        x=price_data.index,
                        y=price_data.values,
                        mode="lines",
                        name=item_data["display"],
                        line=dict(color=colors[i % len(colors)], width=2),
                        hovertemplate=f"{item_data['name']}<br>Date: %{{x}}<br>Price: %{{y:.2f}}<extra></extra>"
                    ))

                yaxis_title = "Normalized Price (Base=100)" if st.session_state.normalize_data else "Price"
                yaxis_type = "log" if st.session_state.use_log_scale else "linear"
                if st.session_state.use_log_scale:
                    yaxis_title += " (Log Scale)"

                fig.update_layout(
                    title="Multiple Asset Comparison",
                    xaxis_title="Date",
                    yaxis_title=yaxis_title,
                    yaxis_type=yaxis_type,
                    height=600,
                    hovermode="x unified",
                    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(255, 255, 255, 0.8)"),
                    template="plotly_white"
                )

                st.plotly_chart(fig, use_container_width=True)

                st.subheader("📊 Performance Statistics")
                stats_data = []
                for ticker, item_data in all_data.items():
                    price_data = item_data["data"]
                    if isinstance(price_data, pd.DataFrame):
                        price_data = price_data.iloc[:, 0]
                    if not price_data.empty:
                        start_price = float(price_data.iloc[0])
                        end_price = float(price_data.iloc[-1])
                        total_return = ((end_price - start_price) / start_price * 100) if start_price > 0 else np.nan
                        if len(price_data) > 1:
                            returns = price_data.pct_change().dropna()
                            volatility = returns.std() * np.sqrt(252) * 100
                        else:
                            volatility = np.nan
                        stats_data.append({
                            "Asset": item_data["name"],
                            "Start Price": start_price,
                            "End Price": end_price,
                            "Total Return %": total_return,
                            "Volatility %": volatility,
                            "Days": len(price_data)
                        })

                if stats_data:
                    stats_df = pd.DataFrame(stats_data)
                    stats_display = stats_df.copy()
                    stats_display["Start Price"] = stats_display["Start Price"].apply(lambda x: format_value(x, decimals))
                    stats_display["End Price"] = stats_display["End Price"].apply(lambda x: format_value(x, decimals))
                    stats_display["Total Return %"] = stats_display["Total Return %"].apply(lambda x: f"{x:.2f}%" if not pd.isna(x) else "N/A")
                    stats_display["Volatility %"] = stats_display["Volatility %"].apply(lambda x: f"{x:.2f}%" if not pd.isna(x) else "N/A")

                    def color_return(val):
                        if isinstance(val, str) and "%" in val and val != "N/A":
                            try:
                                num = float(val.replace("%", ""))
                                if num > 0:
                                    return "color: #10B981; font-weight: bold;"
                                elif num < 0:
                                    return "color: #EF4444; font-weight: bold;"
                            except:
                                pass
                        return ""

                    styled_stats = stats_display.style.map(color_return, subset=["Total Return %"])
                    st.dataframe(styled_stats, use_container_width=True, hide_index=True)

                    st.markdown("---")
                    if st.button("📥 Download Chart Data", use_container_width=True):
                        download_chart_data = []
                        for ticker, item_data in all_data.items():
                            price_data = item_data["data"]
                            if isinstance(price_data, pd.DataFrame):
                                price_data = price_data.iloc[:, 0]
                            for date, price in price_data.items():
                                download_chart_data.append({"Date": date, "Asset": item_data["name"], "Ticker": ticker, "Price": price})

                        if download_chart_data:
                            st.download_button(
                                label="📥 Confirm Download",
                                data=pd.DataFrame(download_chart_data).to_csv(index=False),
                                file_name=f"chart_data_{st.session_state.chart_start_date}_{st.session_state.chart_end_date}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
            else:
                st.warning("❌ No data available for the selected assets in the specified date range.")
        else:
            st.info("💡 Use the sidebar 'Chart Configuration' section to add assets to the chart.")

    st.markdown("---")
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.caption(f"🕒 Last updated: {update_time} | 📊 **Data Source:** Yahoo Finance")
    st.caption(f"📅 Display Period: {selected_start} to {selected_end} | YTD: {ytd_start_date} to {selected_end}")

# ====================== PAGE 3: FX ======================
def render_fx_page():
    st.title("💱 Foreign Exchange")
    st.markdown("### Real-time FX rates, charts, and correlation analysis")

    fx_tab1, fx_tab2, fx_tab3, fx_tab4 = st.tabs(["📊 FX Rates Table", "🔀 Pair Selector", "📈 FX Charts", "🔄 Correlation Matrix"])

    # ========== TAB 1: FX Rates Table (4 columns only) ==========
    with fx_tab1:
        st.header("FX Rates Table")

        col_config1, col_config2, col_config3 = st.columns([2, 2, 1])

        with col_config1:
            all_currencies = list(FX_CURRENCIES["G10 Currencies"].keys()) + list(FX_CURRENCIES["Emerging Currencies"].keys())
            all_currencies = sorted(list(set(all_currencies)))

            fx_table_base_currency = st.selectbox(
                "Base Currency for Table",
                options=all_currencies,
                index=all_currencies.index("USD") if "USD" in all_currencies else 0,
                key="fx_table_base_select",
                help="Select the base currency for the FX rates table"
            )
            st.session_state.fx_table_base_currency = fx_table_base_currency

        with col_config2:
            fx_quote_date = st.date_input(
                "Quote Date",
                value=st.session_state.fx_quote_date,
                key="fx_quote_date_select",
                help="Select the date for FX rates quotation"
            )
            st.session_state.fx_quote_date = fx_quote_date

        with col_config3:
            st.metric("Table Base", fx_table_base_currency)

        st.markdown("---")

        def color_pct(val):
            if isinstance(val, str) and "%" in val and val != "N/A":
                try:
                    num = float(val.replace("%", ""))
                    if num > 0:
                        return "color:#10B981;font-weight:bold;"
                    if num < 0:
                        return "color:#EF4444;font-weight:bold;"
                except:
                    pass
            return ""

        def build_fx_table_4cols(base_ccy, currency_list, quote_date):
            rows = []
            for ccy in currency_list:
                if ccy == base_ccy:
                    continue

                # value at quote date
                rate = get_fx_rate_single_date(base_ccy, ccy, quote_date)

                # 1D % from last two closes up to quote_date
                d1 = np.nan
                ser = get_fx_data(base_ccy, ccy, quote_date - timedelta(days=10), quote_date + timedelta(days=1))
                if ser is not None and not ser.empty:
                    ser2 = ser[ser.index <= pd.Timestamp(quote_date)]
                    if len(ser2) >= 2:
                        last = float(ser2.iloc[-1])
                        prev = float(ser2.iloc[-2])
                        if prev != 0:
                            d1 = (last - prev) / prev * 100

                # YTD %
                ytd_start = datetime(quote_date.year, 1, 1).date()
                ytd_rate = get_fx_rate_single_date(base_ccy, ccy, ytd_start)
                ytd = np.nan
                if rate is not None and ytd_rate is not None and ytd_rate != 0:
                    ytd = (rate - ytd_rate) / ytd_rate * 100

                rows.append({"Pair": f"{base_ccy}/{ccy}", "Value": rate, "1D %": d1, "YTD %": ytd})

            df = pd.DataFrame(rows)
            df_disp = df.copy()
            df_disp["Value"] = df_disp["Value"].apply(lambda x: f"{x:.4f}" if x is not None and not pd.isna(x) else "N/A")
            df_disp["1D %"] = df_disp["1D %"].apply(lambda x: f"{x:.2f}%" if not pd.isna(x) else "N/A")
            df_disp["YTD %"] = df_disp["YTD %"].apply(lambda x: f"{x:.2f}%" if not pd.isna(x) else "N/A")
            return df, df_disp

        # G10
        st.subheader(f"G10 Currencies (vs {fx_table_base_currency})")
        g10_currencies = list(FX_CURRENCIES["G10 Currencies"].keys())
        if fx_table_base_currency in g10_currencies:
            g10_currencies.remove(fx_table_base_currency)

        g10_raw, g10_disp = build_fx_table_4cols(fx_table_base_currency, g10_currencies, fx_quote_date)
        if g10_disp is not None and not g10_disp.empty:
            st.dataframe(g10_disp.style.map(color_pct, subset=["1D %", "YTD %"]), use_container_width=True, hide_index=True)
        else:
            st.warning("No data available for G10.")

        # Emerging
        st.subheader(f"Emerging Currencies (vs {fx_table_base_currency})")
        em_currencies = list(FX_CURRENCIES["Emerging Currencies"].keys())
        if fx_table_base_currency in em_currencies:
            em_currencies.remove(fx_table_base_currency)

        em_raw, em_disp = build_fx_table_4cols(fx_table_base_currency, em_currencies, fx_quote_date)
        if em_disp is not None and not em_disp.empty:
            st.dataframe(em_disp.style.map(color_pct, subset=["1D %", "YTD %"]), use_container_width=True, hide_index=True)
        else:
            st.warning("No data available for Emerging.")

        st.markdown("---")
        if st.button("📥 Download FX Table Data", use_container_width=True):
            out = []
            if g10_raw is not None and not g10_raw.empty:
                out.append(g10_raw)
            if em_raw is not None and not em_raw.empty:
                out.append(em_raw)
            if out:
                combined_df = pd.concat(out, ignore_index=True)
                st.download_button(
                    label="📥 Confirm Download",
                    data=combined_df.to_csv(index=False),
                    file_name=f"fx_rates_{fx_table_base_currency}_{fx_quote_date}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("Nothing to download (no data returned).")

    # ========== TAB 2: Pair selector (unchanged) ==========
    with fx_tab2:
        st.header("FX Pair Selector & Analysis")

        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            all_currencies = list(FX_CURRENCIES["G10 Currencies"].keys()) + list(FX_CURRENCIES["Emerging Currencies"].keys())
            all_currencies = sorted(list(set(all_currencies)))

            fx_base_currency = st.selectbox(
                "Base Currency",
                options=all_currencies,
                index=all_currencies.index("EUR") if "EUR" in all_currencies else 0,
                key="fx_base_select",
                help="Select the base currency for FX pairs"
            )
            st.session_state.fx_base_currency = fx_base_currency

        with col2:
            fx_unit_currency = st.selectbox(
                "Unit Currency",
                options=all_currencies,
                index=all_currencies.index("USD") if "USD" in all_currencies else 0,
                key="fx_unit_select",
                help="Select the unit currency for FX pairs"
            )
            st.session_state.fx_unit_currency = fx_unit_currency

        with col3:
            st.metric("Selected Pair", f"{fx_base_currency}/{fx_unit_currency}")

        st.markdown("---")
        st.subheader(f"{fx_base_currency}/{fx_unit_currency} Analysis")

        current_data = get_fx_data(fx_base_currency, fx_unit_currency, selected_start, selected_end)

        if current_data is not None and not current_data.empty:
            if isinstance(current_data, pd.DataFrame):
                current_data = current_data.iloc[:, 0] if len(current_data.columns) > 0 else pd.Series(dtype=float)

            if not current_data.empty:
                current_rate = float(current_data.iloc[-1])

                if len(current_data) > 1:
                    prev_rate = float(current_data.iloc[-2])
                    daily_change = ((current_rate - prev_rate) / prev_rate * 100) if prev_rate > 0 else 0
                else:
                    daily_change = 0

                ytd_data = get_fx_data(fx_base_currency, fx_unit_currency, ytd_start_date, selected_end)
                if ytd_data is not None and not ytd_data.empty:
                    if isinstance(ytd_data, pd.DataFrame):
                        ytd_data = ytd_data.iloc[:, 0] if len(ytd_data.columns) > 0 else pd.Series(dtype=float)
                    if len(ytd_data) > 1:
                        ytd_start = float(ytd_data.iloc[0])
                        ytd_change = ((current_rate - ytd_start) / ytd_start * 100) if ytd_start > 0 else 0
                    else:
                        ytd_change = np.nan
                else:
                    ytd_change = np.nan

                col_rate1, col_rate2, col_rate3 = st.columns(3)
                with col_rate1:
                    st.metric("Current Rate", f"{current_rate:.4f}", f"{daily_change:+.2f}%")
                with col_rate2:
                    st.metric("YTD Change", f"{ytd_change:.2f}%" if not pd.isna(ytd_change) else "N/A")
                with col_rate3:
                    all_time_high = float(current_data.max())
                    all_time_low = float(current_data.min())
                    st.metric("Range", f"{all_time_low:.4f} - {all_time_high:.4f}", delta_color="off")

                st.subheader(f"{fx_base_currency}/{fx_unit_currency} - Historical Chart")

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=current_data.index,
                    y=current_data.values,
                    mode="lines",
                    name=f"{fx_base_currency}/{fx_unit_currency}",
                    line=dict(width=2),
                    hovertemplate="Rate: %{y:.4f}<br>Date: %{x}<extra></extra>"
                ))
                fig.update_layout(
                    title=f"{fx_base_currency}/{fx_unit_currency} Exchange Rate",
                    xaxis_title="Date",
                    yaxis_title=f"{fx_base_currency}/{fx_unit_currency}",
                    height=400,
                    hovermode="x unified",
                    template="plotly_white"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"No data available for {fx_base_currency}/{fx_unit_currency}")
        else:
            st.warning(f"No data available for {fx_base_currency}/{fx_unit_currency}")

        if current_data is not None and not current_data.empty:
            col_add1, col_add2 = st.columns(2)
            with col_add1:
                if st.button("➕ Add to FX Charts", use_container_width=True):
                    pair_name = f"{fx_base_currency}/{fx_unit_currency}"
                    if not any(item["pair"] == pair_name for item in st.session_state.fx_chart_items):
                        st.session_state.fx_chart_items.append({"pair": pair_name, "base": fx_base_currency, "unit": fx_unit_currency, "display": f"💱 {pair_name}"})
                        st.success(f"Added {pair_name} to FX Charts")
                        st.rerun()
            with col_add2:
                if st.button("📥 Download FX Data", use_container_width=True):
                    df_download = pd.DataFrame({"Date": current_data.index, "Rate": current_data.values})
                    st.download_button(
                        label="📥 Confirm Download",
                        data=df_download.to_csv(index=False),
                        file_name=f"fx_{fx_base_currency}_{fx_unit_currency}_{selected_start}_{selected_end}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

    # ========== TAB 3: FX Charts (unchanged) ==========
    with fx_tab3:
        st.header("📈 FX Interactive Charts")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader("Multiple FX Pairs Comparison")
        with col2:
            if st.button("🗑️ Clear All FX Charts", use_container_width=True):
                st.session_state.fx_chart_items = []
                st.rerun()

        st.markdown("---")

        if st.session_state.fx_chart_items:
            with st.expander("📋 FX Pairs in Chart", expanded=True):
                cols = st.columns(3)
                for i, item in enumerate(list(st.session_state.fx_chart_items)):
                    with cols[i % 3]:
                        container = st.container(border=True)
                        container.write(f"**{item['display']}**")
                        if container.button("❌ Remove", key=f"remove_fx_{item['pair']}"):
                            st.session_state.fx_chart_items.remove(item)
                            st.rerun()

            all_fx_data = {}
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, item in enumerate(st.session_state.fx_chart_items):
                status_text.text(f"Fetching data for {item['pair']}...")
                data = get_fx_data(item["base"], item["unit"], selected_start, selected_end)
                if data is not None and not data.empty:
                    if isinstance(data, pd.DataFrame):
                        data = data.iloc[:, 0] if len(data.columns) > 0 else pd.Series(dtype=float)
                    if not data.empty:
                        all_fx_data[item["pair"]] = {"data": data, "name": item["pair"], "display": item["display"], "base": item["base"], "unit": item["unit"]}
                progress_bar.progress((i + 1) / len(st.session_state.fx_chart_items))

            progress_bar.empty()
            status_text.empty()

            if all_fx_data:
                fig = go.Figure()
                colors = px.colors.qualitative.Set1 + px.colors.qualitative.Set2 + px.colors.qualitative.Set3

                for i, (pair, fx_data) in enumerate(all_fx_data.items()):
                    price_data = fx_data["data"]
                    first_value = float(price_data.iloc[0])
                    normalized_data = (price_data / first_value) * 100 if first_value > 0 else price_data

                    fig.add_trace(go.Scatter(
                        x=price_data.index,
                        y=normalized_data.values,
                        mode="lines",
                        name=fx_data["display"],
                        line=dict(color=colors[i % len(colors)], width=2),
                        hovertemplate=f"{fx_data['name']}<br>Date: %{{x}}<br>Normalized: %{{y:.2f}}<extra></extra>"
                    ))

                fig.update_layout(
                    title="FX Pairs Comparison (Normalized to 100)",
                    xaxis_title="Date",
                    yaxis_title="Normalized Rate (Base=100)",
                    height=500,
                    hovermode="x unified",
                    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(255, 255, 255, 0.8)"),
                    template="plotly_white"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("❌ No data available for the selected FX pairs in the specified date range.")
        else:
            st.info("💡 Use the 'Add to FX Charts' button in the Pair Selector tab to add currency pairs for comparison.")

    # ========== TAB 4: Correlation Matrix (USD included, readable text, USD not blank) ==========
    with fx_tab4:
        st.header("🔄 FX Correlation Matrix")
        st.markdown("Analyze correlation between selected currencies (vs USD).")

        all_currencies = sorted(list(set(
            list(FX_CURRENCIES["G10 Currencies"].keys()) +
            list(FX_CURRENCIES["Emerging Currencies"].keys()) +
            ["USD"]
        )))

        selected_currencies = st.multiselect(
            "Select Currencies:",
            options=all_currencies,
            default=["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY", "INR", "BRL", "MXN"],
            help="Correlation computed on daily returns of FX rates vs USD. USD (if selected) is a basket index."
        )

        base = "USD"

        if selected_currencies and len(selected_currencies) > 1:
            returns_data = {}
            mean_daily_returns = {}

            # non-USD currencies
            for ccy in selected_currencies:
                if ccy == base:
                    continue
                series = get_fx_data(base, ccy, selected_start, selected_end)  # USD vs CCY
                if series is not None and not series.empty and len(series) > 1:
                    rets = series.pct_change().dropna()
                    if not rets.empty:
                        returns_data[ccy] = rets
                        mean_daily_returns[ccy] = float(rets.mean() * 100.0)

            if not returns_data:
                st.warning("No returns data available for the selected currencies in the specified date range.")
            else:
                returns_df = pd.DataFrame(returns_data).dropna(how="any")

                if returns_df.shape[1] < 2 and "USD" not in selected_currencies:
                    st.warning("Need at least 2 currencies with valid data to compute correlation.")
                else:
                    # USD basket series to avoid blank USD row/col
                    if "USD" in selected_currencies:
                        usd_basket = returns_df.mean(axis=1)
                        returns_df["USD"] = usd_basket
                        mean_daily_returns["USD"] = float(usd_basket.mean() * 100.0)

                    ordered_cols = [c for c in selected_currencies if c in returns_df.columns]
                    returns_df = returns_df[ordered_cols]

                    corr_matrix = returns_df.corr()

                    st.subheader("Correlation Matrix (Daily Returns)")
                    st.caption("Each cell shows: correlation with **avg daily return of the column series** in parentheses.")

                    ann = corr_matrix.copy()
                    for col in ann.columns:
                        mu = mean_daily_returns.get(col, np.nan)
                        ann[col] = ann[col].apply(lambda x, _mu=mu: f"{x:.2f}\n({_mu:.2f}%)" if pd.notna(x) else "")

                    fig, ax = plt.subplots(figsize=(11, 8))
                    sns.heatmap(
                        corr_matrix,
                        annot=ann,
                        fmt="",
                        cmap="RdBu_r",
                        center=0,
                        square=True,
                        linewidths=0.5,
                        cbar_kws={"shrink": 0.8},
                        annot_kws={"size": 7},   # ✅ smaller text
                        ax=ax
                    )
                    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
                    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
                    plt.title("FX Correlation Matrix vs USD (Daily Returns)", fontsize=14, pad=16)
                    plt.tight_layout()
                    st.pyplot(fig)

                    vals = corr_matrix.values
                    tri = vals[np.triu_indices_from(vals, k=1)]
                    tri = tri[~np.isnan(tri)]
                    if tri.size:
                        col_stat1, col_stat2, col_stat3 = st.columns(3)
                        with col_stat1:
                            st.metric("Average Correlation", f"{float(tri.mean()):.3f}")
                        with col_stat2:
                            st.metric("Maximum Correlation", f"{float(tri.max()):.3f}")
                        with col_stat3:
                            st.metric("Minimum Correlation", f"{float(tri.min()):.3f}")

                    st.markdown("---")
                    col_dl1, col_dl2 = st.columns(2)
                    with col_dl1:
                        if st.button("📥 Download Correlation Matrix", use_container_width=True):
                            st.download_button(
                                label="📥 Confirm Download",
                                data=corr_matrix.to_csv(),
                                file_name=f"fx_correlation_matrix_USD_{selected_start}_{selected_end}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                    with col_dl2:
                        if st.button("📥 Download Returns Data", use_container_width=True):
                            st.download_button(
                                label="📥 Confirm Download",
                                data=returns_df.to_csv(),
                                file_name=f"fx_returns_data_USD_{selected_start}_{selected_end}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
        else:
            st.info("💡 Please select at least 2 currencies to generate a correlation matrix.")

# ====================== PAGE 4: RATES/BONDS ======================
def render_rates_bonds_page():
    st.title("📊 Rates & Bonds")
    st.markdown("### Money-market rates and sovereign yield curves")

    def color_pct(val):
        if isinstance(val, str) and "%" in val and val != "N/A":
            try:
                num = float(val.replace("%", ""))
                if num > 0:
                    return "color:#10B981;font-weight:bold;"
                if num < 0:
                    return "color:#EF4444;font-weight:bold;"
            except:
                pass
        return ""

    # ---- Short term rates definitions ----
    US_SHORT = [
        {"Instrument": "SOFR (proxy)", "Ticker": "SOFR"},
        {"Instrument": "3M (13W T-Bill)", "Ticker": "^IRX"},
        {"Instrument": "6M (proxy)", "Ticker": "^IRX"},
        {"Instrument": "9M (proxy)", "Ticker": "^IRX"},
        {"Instrument": "1Y (proxy)", "Ticker": "^IRX"},
    ]

    EZ_SHORT = [
        {"Instrument": "ESTR (proxy)", "Ticker": "ESTR"},
        {"Instrument": "3M (proxy)", "Ticker": "EUR3M=X"},
        {"Instrument": "6M (proxy)", "Ticker": "EUR6M=X"},
        {"Instrument": "9M (proxy)", "Ticker": "EUR9M=X"},
        {"Instrument": "1Y (proxy)", "Ticker": "EUR1Y=X"},
    ]

    # ---- Sovereign yields ----
    TENORS = ["2Y", "5Y", "10Y", "20Y", "30Y"]
    COUNTRIES = ["US", "France", "Germany", "UK", "Spain", "Italy", "China", "Japan"]

    # Best-effort Yahoo tickers; replace placeholders with correct ones if you have them
    YIELD_TICKERS = {
        ("US", "2Y"): "^UST2Y",
        ("US", "5Y"): "^FVX",
        ("US", "10Y"): "^TNX",
        ("US", "20Y"): "^TYX",  # proxy
        ("US", "30Y"): "^TYX",

        # placeholders (10Y only) — update later with your preferred tickers/data source
        ("France", "10Y"): "^TNX",
        ("Germany", "10Y"): "^TNX",
        ("UK", "10Y"): "^TNX",
        ("Spain", "10Y"): "^TNX",
        ("Italy", "10Y"): "^TNX",
        ("China", "10Y"): "^TNX",
        ("Japan", "10Y"): "^TNX",
    }

    tab1, tab2 = st.tabs(["💵 Short term rates", "🏛️ Sovereign Yields"])

    # ========== TAB 1: Two separate tables + two charts ==========
    with tab1:
        st.subheader("Short term rates")

        def build_short_table(items):
            rows = []
            for it in items:
                res = get_equity_data(it["Ticker"], selected_start, selected_end, ytd_start_date)
                if res:
                    rows.append({"Instrument": it["Instrument"], "Value": res["Value"], "1D %": res["Daily %"], "YTD %": res["YTD %"]})
                else:
                    rows.append({"Instrument": it["Instrument"], "Value": np.nan, "1D %": np.nan, "YTD %": np.nan})
            df = pd.DataFrame(rows)
            disp = df.copy()
            disp["Value"] = disp["Value"].apply(lambda x: format_nominal(x, st.session_state.decimals))
            disp["1D %"] = disp["1D %"].apply(lambda x: f"{x:.2f}%" if not pd.isna(x) else "N/A")
            disp["YTD %"] = disp["YTD %"].apply(lambda x: f"{x:.2f}%" if not pd.isna(x) else "N/A")
            return df, disp

        # US
        st.markdown("### United States")
        us_df, us_disp = build_short_table(US_SHORT)
        st.dataframe(us_disp.style.map(color_pct, subset=["1D %", "YTD %"]), use_container_width=True, hide_index=True)

        us_chart_start, us_chart_end = st.columns(2)
        with us_chart_start:
            us_start = st.date_input("US chart start", value=selected_start, key="rb_us_start")
        with us_chart_end:
            us_end = st.date_input("US chart end", value=selected_end, key="rb_us_end")

        us_opts = [x["Instrument"] for x in US_SHORT]
        us_sel = st.multiselect("Select US instruments to plot:", options=us_opts, default=[us_opts[0]] if us_opts else [], key="rb_us_sel")

        if us_sel:
            fig = go.Figure()
            colors = px.colors.qualitative.Set1 + px.colors.qualitative.Set2 + px.colors.qualitative.Set3
            for i, inst in enumerate(us_sel):
                ticker = next(x["Ticker"] for x in US_SHORT if x["Instrument"] == inst)
                ser = get_historical_data(ticker, us_start, us_end)
                if ser is not None and not ser.empty:
                    fig.add_trace(go.Scatter(x=ser.index, y=ser.values, mode="lines", name=inst,
                                             line=dict(color=colors[i % len(colors)], width=2)))
            fig.update_layout(title="US Short term rates", xaxis_title="Date", yaxis_title="Value",
                              height=420, hovermode="x unified", template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # EZ
        st.markdown("### Eurozone")
        ez_df, ez_disp = build_short_table(EZ_SHORT)
        st.dataframe(ez_disp.style.map(color_pct, subset=["1D %", "YTD %"]), use_container_width=True, hide_index=True)

        ez_chart_start, ez_chart_end = st.columns(2)
        with ez_chart_start:
            ez_start = st.date_input("EZ chart start", value=selected_start, key="rb_ez_start")
        with ez_chart_end:
            ez_end = st.date_input("EZ chart end", value=selected_end, key="rb_ez_end")

        ez_opts = [x["Instrument"] for x in EZ_SHORT]
        ez_sel = st.multiselect("Select EZ instruments to plot:", options=ez_opts, default=[ez_opts[0]] if ez_opts else [], key="rb_ez_sel")

        if ez_sel:
            fig = go.Figure()
            colors = px.colors.qualitative.Set1 + px.colors.qualitative.Set2 + px.colors.qualitative.Set3
            for i, inst in enumerate(ez_sel):
                ticker = next(x["Ticker"] for x in EZ_SHORT if x["Instrument"] == inst)
                ser = get_historical_data(ticker, ez_start, ez_end)
                if ser is not None and not ser.empty:
                    fig.add_trace(go.Scatter(x=ser.index, y=ser.values, mode="lines", name=inst,
                                             line=dict(color=colors[i % len(colors)], width=2)))
            fig.update_layout(title="Eurozone Short term rates", xaxis_title="Date", yaxis_title="Value",
                              height=420, hovermode="x unified", template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

    # ========== TAB 2: Pivot yield table + chart ==========
    with tab2:
        st.subheader("Sovereign Yields")

        # Build matrix tenor rows, countries columns
        matrix = pd.DataFrame(index=TENORS, columns=COUNTRIES, dtype=float)
        for tenor in TENORS:
            for country in COUNTRIES:
                ticker = YIELD_TICKERS.get((country, tenor))
                if ticker:
                    res = get_equity_data(ticker, selected_start, selected_end, ytd_start_date)
                    matrix.loc[tenor, country] = res["Value"] if res else np.nan
                else:
                    matrix.loc[tenor, country] = np.nan

        disp = matrix.copy()
        for c in disp.columns:
            disp[c] = disp[c].apply(lambda x: format_nominal(x, st.session_state.decimals))
        st.dataframe(disp, use_container_width=True)

        st.markdown("---")
        st.subheader("Yields chart")

        y_start_col, y_end_col = st.columns(2)
        with y_start_col:
            y_start = st.date_input("Yields chart start", value=selected_start, key="rb_y_start")
        with y_end_col:
            y_end = st.date_input("Yields chart end", value=selected_end, key="rb_y_end")

        series_options = []
        series_map = {}
        for tenor in TENORS:
            for country in COUNTRIES:
                ticker = YIELD_TICKERS.get((country, tenor))
                if ticker:
                    lab = f"{country} {tenor}"
                    series_options.append(lab)
                    series_map[lab] = ticker

        default_pick = ["US 10Y"] if "US 10Y" in series_options else (series_options[:1] if series_options else [])
        chosen = st.multiselect("Select series to plot:", options=series_options, default=default_pick, key="rb_y_sel")

        if chosen:
            fig = go.Figure()
            colors = px.colors.qualitative.Set1 + px.colors.qualitative.Set2 + px.colors.qualitative.Set3
            for i, lab in enumerate(chosen):
                ser = get_historical_data(series_map[lab], y_start, y_end)
                if ser is not None and not ser.empty:
                    fig.add_trace(go.Scatter(x=ser.index, y=ser.values, mode="lines", name=lab,
                                             line=dict(color=colors[i % len(colors)], width=2)))
            fig.update_layout(title="Sovereign yields time series", xaxis_title="Date", yaxis_title="Value",
                              height=520, hovermode="x unified", template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Select at least one series to plot.")

# ====================== PAGE 5: COMMODITIES ======================
def render_commodities_page():
    st.title("🛢️ Commodities")
    st.markdown("### Metals, Energy, and Agriculture performance dashboard")

    METALS = [
        {"Category": "Metals", "Name": "Gold", "Ticker": "GC=F"},
        {"Category": "Metals", "Name": "Silver", "Ticker": "SI=F"},
        {"Category": "Metals", "Name": "Copper", "Ticker": "HG=F"},
        {"Category": "Metals", "Name": "Platinum", "Ticker": "PL=F"},
        {"Category": "Metals", "Name": "Palladium", "Ticker": "PA=F"},
    ]

    FOOD = [
        {"Category": "Agriculture", "Name": "Wheat", "Ticker": "ZW=F"},
        {"Category": "Agriculture", "Name": "Corn", "Ticker": "ZC=F"},
        {"Category": "Agriculture", "Name": "Soybeans", "Ticker": "ZS=F"},
        {"Category": "Agriculture", "Name": "Coffee", "Ticker": "KC=F"},
        {"Category": "Agriculture", "Name": "Sugar", "Ticker": "SB=F"},
        {"Category": "Agriculture", "Name": "Cocoa", "Ticker": "CC=F"},
    ]

    ENERGY = [
        {"Category": "Energy", "Name": "WTI Crude Oil", "Ticker": "CL=F"},
        {"Category": "Energy", "Name": "Brent Crude Oil", "Ticker": "BZ=F"},
        {"Category": "Energy", "Name": "Natural Gas", "Ticker": "NG=F"},
        {"Category": "Energy", "Name": "Gasoline", "Ticker": "RB=F"},
    ]

    tab1, tab2, tab3, tab4 = st.tabs(["🥇 Metals", "🌾 Food & Agriculture", "⚡ Energy", "📈 Commodities Chart"])

    def color_pct(val):
        if isinstance(val, str) and "%" in val and val != "N/A":
            try:
                num = float(val.replace("%", ""))
                if num > 0:
                    return "color:#10B981;font-weight:bold;"
                if num < 0:
                    return "color:#EF4444;font-weight:bold;"
            except:
                pass
        return ""

    def make_table(items):
        rows = []
        for it in items:
            res = get_equity_data(it["Ticker"], selected_start, selected_end, ytd_start_date)
            if res:
                rows.append({
                    "Asset": it["Name"],
                    "Value": res["Value"],
                    "1D %": res["Daily %"],
                    "1W %": res["1 Week %"],
                    "YTD %": res["YTD %"],
                })
            else:
                rows.append({"Asset": it["Name"], "Value": np.nan, "1D %": np.nan, "1W %": np.nan, "YTD %": np.nan})

        df = pd.DataFrame(rows)
        df_disp = df.copy()

        # ✅ No ticker column + ✅ nominal values (no K/M)
        df_disp["Value"] = df_disp["Value"].apply(lambda x: format_nominal(x, st.session_state.decimals))
        df_disp["1D %"] = df_disp["1D %"].apply(lambda x: f"{x:.2f}%" if not pd.isna(x) else "N/A")
        df_disp["1W %"] = df_disp["1W %"].apply(lambda x: f"{x:.2f}%" if not pd.isna(x) else "N/A")
        df_disp["YTD %"] = df_disp["YTD %"].apply(lambda x: f"{x:.2f}%" if not pd.isna(x) else "N/A")

        st.dataframe(df_disp.style.map(color_pct, subset=["1D %", "1W %", "YTD %"]),
                     use_container_width=True, hide_index=True)

    with tab1:
        st.subheader(f"Metals (Selected Period: {selected_start} → {selected_end})")
        make_table(METALS)

    with tab2:
        st.subheader(f"Food & Agriculture (Selected Period: {selected_start} → {selected_end})")
        make_table(FOOD)

    with tab3:
        st.subheader(f"Energy (Selected Period: {selected_start} → {selected_end})")
        make_table(ENERGY)

    with tab4:
        st.subheader("📈 Chart (Commodities)")
        st.caption("Choose assets + time length. Optional: normalize to 100 or log scale.")

        universe = METALS + FOOD + ENERGY
        options = [f"{x['Category']} - {x['Name']}" for x in universe]
        opt_map = {f"{x['Category']} - {x['Name']}": x for x in universe}

        c1, c2 = st.columns(2)
        with c1:
            c_start = st.date_input("Chart start", value=selected_start, key="commo_chart_start")
        with c2:
            c_end = st.date_input("Chart end", value=selected_end, key="commo_chart_end")

        c3, c4 = st.columns(2)
        with c3:
            normalize_100 = st.checkbox("Normalize to 100", value=True, key="commo_norm_100")
        with c4:
            use_log = st.checkbox("Log scale", value=False, key="commo_log_scale")

        selected_assets = st.multiselect("Select commodities to chart:", options=options, default=["Metals - Gold"] if "Metals - Gold" in options else [])

        if selected_assets:
            fig = go.Figure()
            colors = px.colors.qualitative.Set1 + px.colors.qualitative.Set2 + px.colors.qualitative.Set3

            for i, lab in enumerate(selected_assets):
                it = opt_map[lab]
                ser = get_historical_data(it["Ticker"], c_start, c_end)
                if ser is None or ser.empty:
                    continue

                if normalize_100:
                    base_val = float(ser.iloc[0])
                    if base_val != 0:
                        ser = (ser / base_val) * 100

                fig.add_trace(go.Scatter(
                    x=ser.index,
                    y=ser.values,
                    mode="lines",
                    name=it["Name"],
                    line=dict(color=colors[i % len(colors)], width=2)
                ))

            fig.update_layout(
                title="Commodities Time Series",
                xaxis_title="Date",
                yaxis_title="Normalized (Base=100)" if normalize_100 else "Value",
                yaxis_type="log" if use_log else "linear",
                height=550,
                hovermode="x unified",
                template="plotly_white"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Add commodities using the selector above to display a chart.")

# ====================== MAIN ROUTING ======================
if st.session_state.page == "My Dashboard":
    render_my_dashboard()
elif st.session_state.page == "Equity":
    render_equity_page()
elif st.session_state.page == "FX":
    render_fx_page()
elif st.session_state.page == "Rates/Bonds":
    render_rates_bonds_page()
elif st.session_state.page == "Commodities":

    render_commodities_page()

