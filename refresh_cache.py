"""
refresh_cache.py — Builds cache/prices.json for ALL tickers (stocks + ETFs)
Priority: IBKR (ibapi) → TradingView Screener → yfinance
Run: python refresh_cache.py
"""
import json, os, time, threading
from datetime import date, datetime

BASE       = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE, "cache", "prices.json")
DATA_FILE  = os.path.join(BASE, "data",  "watchlists.json")
os.makedirs(os.path.join(BASE, "cache"), exist_ok=True)

ETF_TICKERS = sorted(set([
    "AGG","AMLP","ARGT","ARKF","ARKG","ARKK","ARKQ","ARKX","BBH","BETZ",
    "BJK","BLOK","BOAT","BOTZ","BTF","BUZZ","CHIQ","CIBR","CLOU","COPX",
    "DBA","DBC","DRIV","DTCR","DXYZ","EMLC","ENFR","ERTH","ESPO","EVX",
    "EWZ","FDRV","FFTY","FDN","FRI","FTXG","FXI","GDX","GDXJ","GLD",
    "GNR","GRID","GUNR","GXC","IBB","IBUY","IEF","IEI","IEO","IGF",
    "IGV","ICLN","IHF","IHI","IPAY","IPO","ITA","ITB","IWM","IWO",
    "IYC","IYG","IYK","IYR","IYT","IYZ","JNK","JETS","KBE","KCE",
    "KIE","KRE","KRBN","KURE","KWEB","LIT","LQD","MJ","MOO","MSOS",
    "MTUM","NANR","NLR","ONLN","OIH","PBE","PBJ","PBW","PEJ","PHO",
    "PPH","PRNT","QQQ","QQQE","QTUM","REMX","ROBO","RSP","RSPC","RSPD",
    "RSPF","RSPN","RSPH","RSPR","RSPS","RTH","SCHH","SHV","SIL","SILJ",
    "SLV","SLX","SMIN","SMH","SOCL","SOXX","SPY","SPPP","TAN","TLT",
    "TOLZ","UNG","URA","URNM","USO","UUP","UFO","VEGI","VGIT","WCLD",
    "WEAT","WGMI","WOOD","XBI","XES","XHB","XHE","XHS","XLC","XLE",
    "XLF","XLI","XLRE","XLSR","XLU","XLK","XLV","XLY","XME","XOP",
    "XPH","XRT","XSD","XSW","XTL","XTN","IAI","IAK","FCG","IDGT",
]))

def load_stock_tickers():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE) as f:
        data = json.load(f)
    return sorted({t for v in data["themes"].values() for t in v})

def pct_from_list(prices, i_new, i_old):
    try:
        n, o = prices[i_new], prices[i_old]
        if o and o != 0:
            return round((n - o) / abs(o) * 100, 2)
    except: pass
    return None

# ── 1. IBKR (sequential, official ibapi) ──────────────────────────────────────
def fetch_ibkr(tickers):
    try:
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper
        from ibapi.contract import Contract
    except ImportError:
        print("[ibkr] ibapi not installed — run: pip install ibapi")
        return None

    print(f"[ibkr] Connecting to TWS port 7497… ({len(tickers)} tickers, sequential)")
    _lock = threading.Lock()
    _bars = []
    _req_done = threading.Event()
    _connected = threading.Event()

    class IBApp(EWrapper, EClient):
        def __init__(self):
            EWrapper.__init__(self); EClient.__init__(self, self)
        def nextValidId(self, orderId): _connected.set()
        def historicalData(self, reqId, bar):
            with _lock: _bars.append((bar.date, bar.close))
        def historicalDataEnd(self, reqId, start, end): _req_done.set()
        def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
            if errorCode == 162:
                print(f"  [pacing] {ticker} — waiting 12s…"); time.sleep(12); _req_done.set()
            elif reqId > 0 and errorCode not in (2104, 2106, 2158, 2119, 200):
                print(f"  [err{errorCode}] {errorString[:60]}"); _req_done.set()
            elif reqId > 0 and errorCode == 200:
                _req_done.set()

    app = IBApp()
    app.connect("127.0.0.1", 7497, clientId=16)
    threading.Thread(target=app.run, daemon=True).start()
    if not _connected.wait(timeout=15):
        print("[ibkr] Connection timeout"); app.disconnect(); return None

    print("[ibkr] Connected — sequential requests…")
    t0 = time.time(); results = {}; bad = []
    ytd0 = date.today().replace(month=1, day=1)

    for i, ticker in enumerate(tickers):
        with _lock: _bars.clear()
        _req_done.clear()
        c = Contract()
        c.symbol = ticker; c.secType = "STK"; c.exchange = "SMART"; c.currency = "USD"
        app.reqHistoricalData(i+1, c, "", "65 D", "1 day", "TRADES", 1, 1, False, [])
        got = _req_done.wait(timeout=10)
        with _lock: bars = list(_bars)
        if not got or len(bars) < 2:
            bad.append(ticker)
        else:
            pl = [b[1] for b in bars]; dl = [b[0] for b in bars]; n = len(pl)
            chg_ytd = None
            try:
                yp = [p for d_str, p in zip(dl, pl)
                      if datetime.strptime(d_str, "%Y%m%d").date() >= ytd0]
                if len(yp) >= 2: chg_ytd = round((yp[-1]-yp[0])/abs(yp[0])*100, 2)
            except: pass
            results[ticker] = {
                "price":   round(pl[-1], 2),
                "chg_1d":  pct_from_list(pl,-1,-2),
                "chg_1w":  pct_from_list(pl,-1,-6)  if n>=6  else None,
                "chg_1m":  pct_from_list(pl,-1,-22) if n>=22 else None,
                "chg_3m":  pct_from_list(pl,-1,-65) if n>=65 else None,
                "chg_ytd": chg_ytd,
            }
        if (i+1) % 50 == 0:
            elapsed = time.time()-t0
            print(f"[ibkr] {i+1}/{len(tickers)}  ok={len(results)}  {elapsed:.0f}s  ETA={elapsed/(i+1)*(len(tickers)-i-1):.0f}s")
        time.sleep(0.25)

    app.disconnect()
    if bad: print(f"[ibkr] No data ({len(bad)}): {bad[:10]}{'…' if len(bad)>10 else ''}")
    print(f"[ibkr] Done — {len(results)}/{len(tickers)} OK in {time.time()-t0:.0f}s")
    return results if results else None

# ── 2. TradingView Screener fallback ──────────────────────────────────────────
# Gets price + 1D/1W/1M/3M/YTD in ONE batch call per 500 tickers — much faster
# than yfinance's two-pass chunked approach.
#
# Fields used:
#   close      → current price
#   change     → 1D % change (already in %)
#   Perf.W     → 1W % performance
#   Perf.1M    → 1M % performance
#   Perf.3M    → 3M % performance
#   Perf.YTD   → YTD % performance

def fetch_tradingview(tickers):
    try:
        from tradingview_screener import Query, Column
    except ImportError:
        print("[tv] tradingview-screener not installed — run: pip install tradingview-screener")
        return None

    print(f"[tv] Fetching {len(tickers)} tickers via TradingView Screener…")
    results = {}
    BATCH = 500   # TV screener max per query
    t0 = time.time()

    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i+BATCH]
        try:
            count, df = (
                Query()
                .select('name', 'close', 'change', 'Perf.W', 'Perf.1M', 'Perf.3M', 'Perf.YTD')
                .where(Column('name').isin(batch))
                .limit(BATCH)
                .get_scanner_data()
            )
            for _, row in df.iterrows():
                sym = row.get('name') or row.get('ticker', '')
                if not sym: continue
                price = row.get('close')
                if price is None or price != price: continue  # NaN check
                def safe(val, scale=1.0):
                    if val is None or val != val: return None
                    return round(float(val) * scale, 2)
                results[sym] = {
                    "price":   round(float(price), 2),
                    "chg_1d":  safe(row.get('change')),
                    "chg_1w":  safe(row.get('Perf.W')),
                    "chg_1m":  safe(row.get('Perf.1M')),
                    "chg_3m":  safe(row.get('Perf.3M')),
                    "chg_ytd": safe(row.get('Perf.YTD')),
                }
            print(f"[tv] batch {i//BATCH+1}: {len(df)} rows returned ({time.time()-t0:.1f}s)")
        except Exception as e:
            print(f"[tv] batch {i//BATCH+1} error: {e}")
            return None  # if TV fails, don't return partial — fall through to yfinance

    # check coverage
    missing = [t for t in tickers if t not in results]
    if missing:
        print(f"[tv] {len(missing)} tickers not found in TV: {missing[:15]}")
    print(f"[tv] Done — {len(results)}/{len(tickers)} tickers in {time.time()-t0:.1f}s")
    return results if results else None

# ── 3. yfinance last-resort fallback ──────────────────────────────────────────
def fetch_yfinance(tickers):
    import yfinance as yf
    import pandas as pd
    print(f"[yfinance] Fetching {len(tickers)} tickers (last resort)…")
    results = {}; CHUNK = 50; ytd0 = date.today().replace(month=1, day=1)

    for i in range(0, len(tickers), CHUNK):
        chunk = tickers[i:i+CHUNK]
        try:
            raw = yf.download(chunk, period="35d", interval="1d",
                              auto_adjust=True, progress=False, threads=True)
            close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
            if len(chunk)==1: close = close.to_frame(name=chunk[0])
            for t in chunk:
                try:
                    s = close[t].dropna(); pl = list(s.values)
                    if not pl: continue
                    results[t] = {"price": round(float(pl[-1]),2),
                                   "chg_1d": pct_from_list(pl,-1,-2),
                                   "chg_1w": pct_from_list(pl,-1,-6) if len(pl)>=6 else None,
                                   "chg_1m": pct_from_list(pl,-1,-22) if len(pl)>=22 else None,
                                   "chg_3m": None, "chg_ytd": None}
                except: pass
        except Exception as e: print(f"[yf] chunk err: {e}")
        time.sleep(0.3)
        print(f"[yfinance] {min(i+CHUNK,len(tickers))}/{len(tickers)}")

    for i in range(0, len(tickers), CHUNK):
        chunk = tickers[i:i+CHUNK]
        try:
            raw = yf.download(chunk, period="1y", interval="1d",
                              auto_adjust=True, progress=False, threads=True)
            close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
            if len(chunk)==1: close = close.to_frame(name=chunk[0])
            for t in chunk:
                try:
                    s = close[t].dropna(); pl = list(s.values)
                    c3m = pct_from_list(pl,-1,-65) if len(pl)>=65 else pct_from_list(pl,-1,0)
                    cytd = None
                    try:
                        sy = s[s.index.date >= ytd0]
                        if len(sy)>=2: cytd = pct_from_list(list(sy.values),-1,0)
                    except: pass
                    if t in results: results[t]["chg_3m"]=c3m; results[t]["chg_ytd"]=cytd
                except: pass
        except Exception as e: print(f"[yf] long chunk err: {e}")
        time.sleep(0.3)

    print(f"[yfinance] Done — {len(results)} tickers")
    return results

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    stock_tickers = load_stock_tickers()
    all_tickers   = sorted(set(stock_tickers + list(ETF_TICKERS)))
    print(f"[info] {len(stock_tickers)} stocks + {len(ETF_TICKERS)} ETFs = {len(all_tickers)} unique total")

    results = None; source = "yfinance"

    # 1. Try IBKR
    try:
        results = fetch_ibkr(all_tickers)
        if results: source = "ibkr"
    except ImportError: print("[info] ibapi not installed")
    except Exception as e: print(f"[ibkr] Error: {e}")

    # 2. Try TradingView Screener
    if not results:
        print("[info] IBKR unavailable — trying TradingView Screener…")
        try:
            results = fetch_tradingview(all_tickers)
            if results: source = "tradingview"
        except Exception as e: print(f"[tv] Error: {e}")

    # 3. Last resort: yfinance
    if not results:
        print("[info] TradingView unavailable — falling back to yfinance…")
        results = fetch_yfinance(all_tickers)

    payload = {
        "updated_date": date.today().isoformat(),
        "updated_at":   datetime.now().isoformat(),
        "source":       source,
        "tickers":      results,
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"\n✓ {len(results)} tickers → {CACHE_FILE}  (source={source})")
    print("  Restart app.py OR click ⟳ in the topbar.")
