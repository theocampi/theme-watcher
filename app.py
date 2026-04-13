"""
WATCHLIST BUILDER — STOCKS + ETFs
Run: python app.py | http://localhost:5051
"""
import json, os
from datetime import datetime, date as _date
from flask import Flask, render_template_string, jsonify, request
import yfinance as yf
import requests
from bs4 import BeautifulSoup

# ── Vercel / Redis config ──────────────────────────────────────────────────
IS_VERCEL     = bool(os.environ.get("VERCEL"))
UPLOAD_SECRET = os.environ.get("UPLOAD_SECRET","changeme")

def _redis_client():
    url = os.environ.get("REDIS_URL")
    if not url: return None
    try:
        import redis as _r
        return _r.from_url(url, decode_responses=True, socket_timeout=4)
    except: return None

def kv_get(key):
    try:
        r = _redis_client()
        return r.get(key) if r else None
    except: return None

def kv_set(key, value):
    try:
        r = _redis_client()
        if r: r.set(key, value)
    except: pass

app  = Flask(__name__)
BASE = "/tmp" if IS_VERCEL else os.path.dirname(os.path.abspath(__file__))
DATA_FILE  = os.path.join(BASE, "data",  "watchlists.json")
CACHE_FILE = os.path.join(BASE, "cache", "prices.json")
os.makedirs(os.path.join(BASE, "data"),  exist_ok=True)
os.makedirs(os.path.join(BASE, "cache"), exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

# ── Stock themes ───────────────────────────────────────────────────────────────
DEFAULT_WATCHLISTS = {"themes": {
    "Aerospace & Defense": ["PLTR","RKLB","HWM","ACHR","AVAV","HEI","NOC","LOAR","KTOS","LHX","RTX","LMT","GD","TDG","BAH","LDOS","CW","BWXT","SAIC","TXT"],
    "AI Health": ["TEM","WGS","BFLY","TDOC","OSCR","TALK","GH","RXRX","ABSI","GRAL","CERT","ALKS","BEAM","VCYT","SDGR","VEEV","DOCS","FLGT","IQV"],
    "AI Insurance": ["ROOT","HIPO","UPST","LMND","GSHD","PRCH","TIPT","LPRO","KNSL","ACGL"],
    "Artificial Intelligence": ["SOUN","TEM","BBAI","ALAB","TSLA","SMTC","AVGO","VRT","AI","GOOGL","AISP","SNOW","ARM","MSFT","META","AMZN","ORCL","IBM","NVDA","PLTR","APP","S","CRNC","TWLO","TEAM","DT","SPT","PDYN","CRM","NOW","ADBE","RBLX","U","GTLB"],
    "Power Generation": ["OKLO","BE","NNE","VST","CEG","GEV","NRG","ASPI","SMR","TLN","AEP","NEE","SO","ETR","EXC","PPL"],
    "Apparel": ["ONON","RL","UAA","ANF","GOOS","URBN","NKE","LULU","TPR","CPRI","GIII","PVH","DECK","CROX"],
    "Argentina": ["MELI","YPF","GGAL","BMA","TX","LOMA","PAM","TGS"],
    "Augmented Reality": ["SNAP","MVIS","GGRP","VUZI","WIMI","META","AAPL"],
    "EV & Battery": ["KULR","MVST","LITM","AMPX","ABAT","TSLA","EOSE","RIVN","LCID","F","GM","BLNK","CHPT","WBX","QS"],
    "Banking & Finance": ["JPM","BAC","C","GS","WFC","SOFI","KEY","UPST","MS","BLK","SCHW","ICE","USB","COF","AXP"],
    "Big Tech / Mega Cap": ["AAPL","AMZN","MSFT","GOOGL","META","SNAP","PINS","NVDA","NFLX","TSLA"],
    "Biotechnology": ["AMGN","GILD","BIIB","REGN","VRTX","CRSP","IONS","SRPT","EXEL","MRNA","BNTX","RGEN","ABBV","ALNY"],
    "BNPL & Payments": ["KPLT","XYZ","SEZL","AFRM","PYPL","V","MA","TOST","FOUR"],
    "Cannabis": ["CGC","ACB","CRON","TLRY","IIPR","SMG","GTBIF","CURLF","TCNNF"],
    "Travel & Entertainment": ["CCL","RCL","DAL","AAL","DIS","NCLH","JBLU","CNK","UAL","LUV","LYV","BKNG","ABNB","EXPE"],
    "Cryptocurrency": ["COIN","MARA","RIOT","MSTR","CLSK","HUT","HOOD","BTBT","APLD","CORZ","IREN","WULF","CIFR","BKKT"],
    "Cloud Computing": ["DDOG","SNOW","NET","NOW","VEEV","DOCN","FSLY","GTLB","MDB","AMZN","MSFT","GOOGL","ORCL","ESTC"],
    "Cybersecurity": ["PANW","FTNT","CRWD","ZS","OKTA","S","NET","BBAI","CHKP","RBRK","QLYS","TENB","RPD","VRNS","SAIL"],
    "Coal": ["CNR","ARLP","AMR","BTU","SXC","HNRG","METC","HCC"],
    "Farming Machinery": ["DE","AGCO","LNN","TWI","TRMB","WTS"],
    "Fertilizer & Crop Inputs": ["CF","NTR","MOS","IPI","CTVA","CMP","LXU","SMG"],
    "Homebuilding": ["DHI","LEN","PHM","TOL","KBH","MTH","CCS","SDHC","FOR","NVR","TMHC"],
    "Industrial Metals": ["FCX","BHP","RIO","VALE","CLF","AA","NUE","STLD","CMC","TROX","TECK"],
    "Lithium": ["ALB","SQM","LAC","SLI","INR","SGML"],
    "Marine Shipping": ["ZIM","MATX","FRO","SFL","DAC","SBLK","SB","DSX"],
    "Magnificent 7 & Growth": ["NVDA","AAPL","NFLX","META","MSFT","AMZN","GOOGL","TSLA","AVGO","APP"],
    "Meme Stocks": ["GME","AMC","BB","KOSS","CLOV","PLTR"],
    "Mortgage Originators": ["RKT","LDI","UWMC","PFSI","OPFI","ESNT","NMIH"],
    "Nuclear & Uranium": ["CCJ","SMR","UEC","VST","OKLO","CEG","LEU","ASPI","NNE","LTBR","TLN","NXE","DNN","UUUU","GLATF"],
    "Optics & Photonics": ["AAOI","LITE","CIEN","IPGP","VIAV","FN","OFS","AMKR","COHR"],
    "Precious Metals": ["NEM","BVN","AEM","KGC","HL","RGLD","PAAS","EQX","AGI","WPM","FNV","AG","CDE","BTG"],
    "Quantum Computing": ["IONQ","RGTI","QBTS","QUBT","IBM","GOOGL","MSFT","HON","ARQQ"],
    "Rare Earth": ["MP","TMC","NB","OMEX","UAMY","PPTA","UUUU","CRML","AMRRY","LYSCF"],
    "Retail & Consumer Brands": ["ULTA","LULU","DKS","SBUX","KO","M","CHWY","WEN","SAM","BROS","BRBR","ELF","WRBY","ODD"],
    "Restaurants & Fast Casual": ["CMG","CAVA","BROS","SG","SHAK","WING","KRUS","VITL","SFM","YUM","FWRG","PTLO","DIN"],
    "Robotics": ["ISRG","SYM","SERV","PDYN","ARBE","MBOT","TSLA","RR","TER","ZBRA","CGNX","PATH","AXON"],
    "Semiconductors": ["NVDA","TSM","AVGO","QCOM","AMD","ARM","AMAT","ALAB","KLAC","LRCX","MRVL","SMCI","CRDO","CRWV","INTC","MU","ASML","ON","TXN","NXPI","MCHP","MPWR","WOLF","SLAB","SNPS","CDNS"],
    "Solar Energy": ["FSLR","SEDG","ENPH","RUN","SHLS","CSIQ","ARRY","NXT","FLNC","SPWR","MAXN"],
    "Space": ["DXYZ","RKLB","LUNR","AMPG","RDW","PL","GSAT","ASTS","SPCE","BKSY","SPIR","SATL","MNTS"],
    "Subscriptions": ["DUOL","SPOT","UBER","NFLX","LYFT","MTCH","BMBL","NRDS","DBX"],
    "Weight Loss / GLP-1": ["NVO","LLY","HIMS","AXSM","VKTX","RYTM","GPCR","TERN","ALT","AMGN"],
    "China": ["BABA","PDD","JD","XPEV","LI","NIO","GOTU","MNSO","PONY","HSAI","BILI","BEKE","TME","BIDU","NTES","TCOM","FUTU","EDU"],
    "Video Games": ["TTWO","U","SE","EA","RBLX","NTES","PLTK","MSFT"],
    "Social Media": ["META","PINS","RDDT","SNAP","BILI","GOOGL","BMBL","MTCH","BIDU","SPOT"],
    "Oil & Gas": ["WMB","LB","AR","EQT","CRK","XOM","CVX","SHEL","TRGP","CTRA","SLB","KMI","PSX","OXY","COP","MPC","VLO","DVN","EOG","HAL","BKR"],
    "Lidar": ["HSAI","INVZ","AEVA","OUST","MVIS","LPTH","FRSX","LIDR"],
    "5G & Telecom": ["QCOM","NOK","ERIC","AVGO","SWKS","KEYS","TMUS","VZ","T","VIAV","QRVO","AMT"],
    "Drones & eVTOL": ["NOC","AVAV","KTOS","EH","RCAT","PDYN","UMAC","ZENA","UAVS","SPAI","AXON","JOBY","TXT","LDOS","ACHR"],
    "ADHD": ["JAZZ","CORT","PRGO","INCY","SUPN"],
    "MPOX": ["MRNA","PFE","JNJ","SNY","GILD","EBS"],
    "Trump Trades": ["DJT","RUM","HOOD","GEO","CXW","AXON","RGR","AOUT"],
    "Real Estate Brokers": ["RMAX","Z","OPEN","EXPI","COMP","REAX","CBRE","JLL"],
    "IPOs": ["GEV","CAVA","GRAL","NNE","SEZL","SN","SNDK","TTAN","TEM","GRND","CRWV","RDDT","KVYO","ARM","RBRK","WAY"],
    "3D Printing": ["XMTR","PRLB","SSYS","DDD","MTLS","NNDM"],
}}
DEFAULT_WATCHLISTS["order"] = list(DEFAULT_WATCHLISTS["themes"].keys())

# ── ETF flat list ──────────────────────────────────────────────────────────────
ETF_LIST = [
    ("SPY","Market"),("QQQ","Market"),("RSP","Market"),("QQQE","Market"),("IWM","Market"),("IWO","Market"),("XLSR","Market"),("FFTY","Market"),
    ("XLK","Tech"),("IGV","Tech"),("XSW","Tech"),("CLOU","Tech"),("WCLD","Tech"),("FDN","Tech"),("IDGT","Tech"),("DXYZ","Tech"),
    ("SMH","Semi"),("SOXX","Semi"),("XSD","Semi"),("GRID","Semi"),
    ("XLE","Energy"),("ENFR","Energy"),("AMLP","Energy"),("TOLZ","Energy"),
    ("IEO","Oil"),("XOP","Oil"),("USO","Oil"),("XES","Oil"),("OIH","Oil"),
    ("FCG","Nat Gas"),("UNG","Nat Gas"),
    ("XTL","Telecom"),("IYZ","Telecom"),
    ("DBC","Cmdty"),("DBA","Cmdty"),("GUNR","Cmdty"),("GNR","Cmdty"),("NANR","Cmdty"),
    ("MOO","Agri"),("VEGI","Agri"),("WEAT","Agri"),
    ("GLD","Gold"),("GDX","Gold"),("GDXJ","Gold"),
    ("SLV","Silver"),("SIL","Silver"),("SILJ","Silver"),("SPPP","Silver"),
    ("XME","Metals"),("SLX","Metals"),("COPX","Metals"),("REMX","Metals"),("LIT","Metals"),
    ("URA","Uranium"),("NLR","Uranium"),("URNM","Uranium"),
    ("ICLN","Clean"),("PBW","Clean"),("TAN","Clean"),("ERTH","Clean"),
    ("XBI","Biotech"),("IBB","Biotech"),("BBH","Biotech"),("PBE","Biotech"),("ARKG","Biotech"),
    ("XLV","Health"),("XHS","Health"),("XHE","Health"),("IHF","Health"),("IHI","Health"),("RSPH","Health"),("XPH","Health"),("PPH","Health"),
    ("XLF","Finance"),("RSPF","Finance"),("IYG","Finance"),("KCE","Finance"),("IAI","Finance"),("KBE","Finance"),("KRE","Finance"),("KIE","Finance"),("IAK","Finance"),
    ("XLRE","RE"),("IYR","RE"),("FRI","RE"),("SCHH","RE"),("RSPR","RE"),("DTCR","RE"),
    ("XLY","Cons D"),("IYC","Cons D"),("RSPD","Cons D"),("XRT","Cons D"),("RTH","Cons D"),("PEJ","Cons D"),("ONLN","Cons D"),("IBUY","Cons D"),
    ("XLP","Cons S"),("IYK","Cons S"),("RSPS","Cons S"),("PBJ","Cons S"),("FTXG","Cons S"),
    ("XLI","Indus"),("RSPN","Indus"),("ITA","Indus"),
    ("IYT","Trans"),("XTN","Trans"),("JETS","Trans"),
    ("IGF","Infra"),("PAVE","Infra"),
    ("XLC","Comm"),("RSPC","Comm"),
    ("XLU","Util"),("XLB","Matrl"),
    ("XHB","Build"),("ITB","Build"),
    ("FXI","China"),("GXC","China"),("KWEB","China"),("CHIQ","China"),("KURE","China"),
    ("EWZ","Intl"),("SMIN","Intl"),("ARGT","Intl"),("EMLC","Intl"),
    ("SHV","Bonds"),("IEI","Bonds"),("VGIT","Bonds"),("IEF","Bonds"),("TLT","Bonds"),("JNK","Bonds"),("AGG","Bonds"),("LQD","Bonds"),
    ("BOTZ","Robo"),("ROBO","Robo"),("ARKQ","Robo"),("PRNT","Robo"),
    ("ARKK","ARK"),("ARKF","ARK"),("ARKX","ARK"),
    ("FDRV","EV"),("DRIV","EV"),
    ("BTF","Crypto"),("WGMI","Crypto"),("BLOK","Crypto"),
    ("MSOS","Cannabis"),("MJ","Cannabis"),
    ("BETZ","Gaming"),("BJK","Gaming"),("ESPO","Gaming"),
    ("CIBR","Cyber"),("UFO","Space"),("QTUM","Quantum"),
    ("SOCL","Social"),("BUZZ","Social"),
    ("IPAY","Fintech"),("PHO","Water"),("WOOD","Timber"),
    ("EVX","Enviro"),("KRBN","Enviro"),
    ("MTUM","Factor"),("UUP","Dollar"),
    ("BOAT","Ship"),("IPO","IPO"),
]
ETF_TICKERS = [t for t,_ in ETF_LIST]
ETF_SECTOR  = {t:s for t,s in ETF_LIST}
ETF_NAMES = {
  "SPY":"SPDR S&P 500","DBC":"Invesco DB Commodity","IDGT":"iShares US Digital Infra","IEO":"iShares US O&G E&P","XTL":"SPDR S&P Telecom","XLE":"Energy Select SPDR","XLK":"Technology Select SPDR","QQQ":"Invesco QQQ","USO":"US Oil Fund","XOP":"SPDR S&P Oil & Gas","FCG":"FT Natural Gas","DBA":"Invesco DB Agriculture","ENFR":"ALPS Alerian Energy Infra","AMLP":"Alerian MLP","XES":"SPDR S&P Oil & Gas E&S","SHV":"iShares 0-1Y Treasury","CLOU":"Global X Cloud Computing","FDN":"FT DJ Internet","IPO":"Renaissance IPO","IEI":"iShares 3-7Y Treasury","VGIT":"Vanguard Interm Treasury","IEF":"iShares 7-10Y Treasury","JNK":"SPDR Bloomberg HY Bond","AGG":"iShares Core US Aggregate","MTUM":"iShares MSCI USA Momentum","LQD":"iShares iBoxx IG Corp","UUP":"Invesco DB USD Index","UFO":"Procure Space ETF","UNG":"US Natural Gas Fund","IYZ":"iShares US Telecom","CIBR":"FT Nasdaq Cybersecurity","OIH":"VanEck Oil Services","XLU":"Utilities Select SPDR","BUZZ":"VanEck Social Sentiment","WEAT":"Teucrium Wheat","ARKF":"ARK Fintech Innovation","BTF":"CoinShares BTC & ETH","ARKX":"ARK Space & Defense","IGF":"iShares Global Infra","WCLD":"WisdomTree Cloud","DTCR":"Global X Data Centers","QQQE":"Direxion NASDAQ-100 EWI","TOLZ":"ProShares DJ Infra","BOAT":"Tidal Global Shipping","MOO":"VanEck Agribusiness","ICLN":"iShares Global Clean Energy","GUNR":"FlexShares Natural Resources","IGV":"iShares Expanded Tech-Software","VEGI":"iShares MSCI Agri Producers","FRI":"FT S&P REIT Index","GNR":"SPDR S&P Global Natural Resources","BLOK":"Amplify Blockchain Tech","XSW":"SPDR S&P Software & Services","ONLN":"ProShares Online Retail","BETZ":"Roundhill Sports Betting","TLT":"iShares 20+ Year Treasury","ARKK":"ARK Innovation","TAN":"Invesco Solar","ESPO":"VanEck Video Games & Esports","NANR":"SPDR S&P NA Natural Resources","XLSR":"SPDR SSGA US Sector Rotation","ARKQ":"ARK Autonomous Tech & Robotics","MSOS":"AdvisorShares Pure US Cannabis","WGMI":"CoinShares Bitcoin Mining","SCHH":"Schwab US REIT","SMH":"VanEck Semiconductor","ERTH":"Invesco MSCI Sustainable Future","KURE":"KraneShares MSCI China HC","XLC":"Communication Services SPDR","ARGT":"Global X MSCI Argentina","FXI":"iShares China Large Cap","RSPC":"Invesco S&P 500 EW Comm Svcs","SOXX":"iShares Semiconductor","GRID":"FT Nasdaq Clean Edge Smart Grid","QTUM":"Defiance Quantum ETF","XLRE":"Real Estate Select SPDR","CHIQ":"Global X MSCI China Cons Disc","IYR":"iShares US Real Estate","PBJ":"Invesco Food & Beverage","ITA":"iShares US Aerospace & Defense","EWZ":"iShares MSCI Brazil","PBW":"Invesco WilderHill Clean Energy","FDRV":"Fidelity Electric Vehicles","IAI":"iShares US Broker-Dealers","XBI":"SPDR S&P Biotech","GXC":"SPDR S&P China","XSD":"SPDR S&P Semiconductor","EMLC":"VanEck EM Local Currency Bond","IBUY":"Amplify Online Retail","KIE":"SPDR S&P Insurance","DRIV":"Global X Autonomous & EV","XHS":"SPDR S&P Health Care Services","DXYZ":"Destiny Tech100","PBE":"Invesco Biotech & Genome","RSP":"Invesco S&P 500 Equal Weight","XLF":"Financial Select SPDR","KCE":"SPDR S&P Capital Markets","SLV":"iShares Silver Trust","IHF":"iShares US Healthcare Providers","RSPR":"Invesco S&P 500 EW Real Estate","RSPF":"Invesco S&P 500 EW Financials","IHI":"iShares US Medical Devices","IYG":"iShares US Financial Services","GLD":"SPDR Gold","LIT":"Global X Lithium & Battery Tech","MJ":"Amplify Alternative Harvest","KWEB":"KraneShares CSI China Internet","ROBO":"ROBO Global Robotics & Automation","IWO":"iShares Russell 2000 Growth","XLI":"Industrials Select SPDR","IYT":"iShares US Transportation","PAVE":"Global X US Infrastructure Dev","RSPN":"Invesco S&P 500 EW Industrials","PEJ":"Invesco Leisure & Entertainment","XTN":"SPDR S&P Transportation","REMX":"VanEck Rare Earth & Strategic Metals","PRNT":"3D Printing ETF","ARKG":"ARK Genomic Revolution","XHE":"SPDR S&P Health Care Equipment","KBE":"SPDR S&P Bank","JETS":"US Global Jets","BJK":"VanEck Gaming","IPAY":"Amplify Digital Payments","NLR":"VanEck Uranium & Nuclear","URA":"Global X Uranium","IYC":"iShares US Consumer Discretionary","KRE":"SPDR S&P Regional Banking","FFTY":"Innovator IBD 50","IBB":"iShares Biotechnology","KRBN":"KraneShares Global Carbon","RTH":"VanEck Retail","SLX":"VanEck Steel","SOCL":"Global X Social Media","BOTZ":"Global X Robotics & AI","SMIN":"iShares MSCI India Small-Cap","RSPH":"Invesco S&P 500 EW Healthcare","IWM":"iShares Russell 2000","IAK":"iShares US Insurance","XHB":"SPDR S&P Homebuilders","SIL":"Global X Silver Miners","SILJ":"Amplify Jr Silver Miners","SPPP":"Sprott Platinum & Palladium","GDXJ":"VanEck Junior Gold Miners","GDX":"VanEck Gold Miners","BBH":"VanEck Biotech","XME":"SPDR S&P Metals & Mining","URNM":"Sprott Uranium Miners","COPX":"Global X Copper Miners","XPH":"SPDR S&P Pharmaceuticals","XLV":"Health Care Select SPDR","XLY":"Consumer Discr Select SPDR","EVX":"VanEck Environmental Services","IYK":"iShares US Consumer Staples","XLB":"Materials Select SPDR","PPH":"VanEck Pharmaceutical","WOOD":"iShares Global Timber","XLP":"Consumer Staples Select SPDR","FTXG":"FT Nasdaq Food & Beverage","RSPS":"Invesco S&P 500 EW Cons Staples","PHO":"Invesco Water Resources","XRT":"SPDR S&P Retail","RSPD":"Invesco S&P 500 EW Cons Disc","ITB":"iShares US Home Construction",
}


# ── Persistence ────────────────────────────────────────────────────────────────
def load_watchlists():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f: return json.load(f)
        except: pass
    raw = kv_get("watchlists")
    if raw:
        try:
            data = json.loads(raw)
            try:
                with open(DATA_FILE,"w") as f: json.dump(data,f,indent=2)
            except: pass
            return data
        except: pass
    save_watchlists(DEFAULT_WATCHLISTS); return DEFAULT_WATCHLISTS

def save_watchlists(data):
    try:
        with open(DATA_FILE,"w") as f: json.dump(data,f,indent=2)
    except: pass
    kv_set("watchlists", json.dumps(data))

# ── Cache ──────────────────────────────────────────────────────────────────────
_fc={};_cm={"date":None,"source":None,"loaded_at":None};_lc={};_ec={}
LIVE_TTL=300;EXT_TTL=14400

def _load_file_cache():
    global _fc,_cm
    try:
        raw=json.load(open(CACHE_FILE))
        _fc=raw.get("tickers",{});_cm.update(date=raw.get("updated_date"),source=raw.get("source"),loaded_at=datetime.now())
        print(f"[cache] {len(_fc)} tickers  date={_cm['date']}  src={_cm['source']}")
    except FileNotFoundError:
        raw = kv_get("prices_cache")
        if raw:
            try:
                data = json.loads(raw)
                _fc = data.get("tickers",{})
                _cm.update(date=data.get("updated_date"), source=data.get("source","redis")+"(kv)", loaded_at=datetime.now())
                print(f"[cache] Redis {len(_fc)} tickers  date={_cm['date']}")
                try:
                    with open(CACHE_FILE,"w") as f: json.dump(data,f)
                except: pass
            except Exception as ex: print(f"[cache] Redis parse error: {ex}")
        else: print("[cache] No cache — yfinance fallback.")
    except Exception as e: print(f"[cache] Error: {e}")

def _fresh(): return bool(_fc and _cm["date"]==_date.today().isoformat())

def _pct(s,a,b):
    try:
        n,o=float(s.iloc[a]),float(s.iloc[b])
        return round((n-o)/abs(o)*100,2) if o else None
    except: return None

def _live_fetch(tickers):
    now=datetime.now()
    need=[t for t in tickers if t not in _lc or (now-_lc[t]["fa"]).total_seconds()>LIVE_TTL]
    if not need: return
    try:
        import pandas as pd
        raw=yf.download(need,period="35d",interval="1d",auto_adjust=True,progress=False,threads=True)
        cl=raw["Close"] if isinstance(raw.columns,pd.MultiIndex) else raw
        if len(need)==1: cl=cl.to_frame(name=need[0])
        for t in need:
            try:
                s=cl[t].dropna()
                _lc[t]={"price":round(float(s.iloc[-1]),2) if len(s)>=1 else None,"chg_1d":_pct(s,-1,-2),"chg_1w":_pct(s,-1,-6) if len(s)>=6 else None,"chg_1m":_pct(s,-1,-22) if len(s)>=22 else None,"fa":now}
            except: _lc[t]={"price":None,"chg_1d":None,"chg_1w":None,"chg_1m":None,"fa":now}
    except:
        for t in need: _lc[t]={"price":None,"chg_1d":None,"chg_1w":None,"chg_1m":None,"fa":datetime.now()}

def _ext_fetch(tickers):
    now=datetime.now()
    need=[t for t in tickers if t not in _ec or (now-_ec[t]["fa"]).total_seconds()>EXT_TTL]
    if not need: return
    try:
        import pandas as pd
        raw=yf.download(need,period="1y",interval="1d",auto_adjust=True,progress=False,threads=True)
        cl=raw["Close"] if isinstance(raw.columns,pd.MultiIndex) else raw
        if len(need)==1: cl=cl.to_frame(name=need[0])
        ytd0=_date.today().replace(month=1,day=1)
        for t in need:
            try:
                s=cl[t].dropna()
                c3m=_pct(s,-1,-65) if len(s)>=65 else _pct(s,-1,0)
                cy=None
                try:
                    sy=s[s.index.date>=ytd0]
                    if len(sy)>=2: cy=_pct(sy,-1,0)
                except: pass
                _ec[t]={"chg_3m":c3m,"chg_ytd":cy,"fa":now}
            except: _ec[t]={"chg_3m":None,"chg_ytd":None,"fa":now}
    except:
        for t in need: _ec[t]={"chg_3m":None,"chg_ytd":None,"fa":datetime.now()}

def fetch_prices(tickers):
    if _cm["loaded_at"] is None: _load_file_cache()
    else:
        try:
            if datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))>_cm["loaded_at"]: _load_file_cache()
        except FileNotFoundError: pass
    result,miss={},[]
    for t in tickers:
        if t in _fc and _fc[t].get("price") is not None: result[t]=_fc[t]
        else: miss.append(t)
    if miss and not IS_VERCEL:
        _live_fetch(miss)
        for t in miss:
            if t in _lc: result[t]={k:v for k,v in _lc[t].items() if k!="fa"}
    return result

def fetch_ext(tickers):
    result,need={},[]
    for t in tickers:
        fc=_fc.get(t,{})
        if fc.get("chg_3m") is not None or fc.get("chg_ytd") is not None: result[t]={"chg_3m":fc.get("chg_3m"),"chg_ytd":fc.get("chg_ytd")}
        else: need.append(t)
    if need and not IS_VERCEL:
        _ext_fetch(need)
        for t in need:
            if t in _ec: result[t]={"chg_3m":_ec[t]["chg_3m"],"chg_ytd":_ec[t]["chg_ytd"]}
    return result

# ── RS Universe ────────────────────────────────────────────────────────────────
_rs_s={};_rs_s_at=None;_rs_e={};_rs_e_at=None;RS_TTL=3600

def _build_rs(tickers):
    prices=fetch_prices(tickers)
    pairs=[(t,prices[t]["chg_1m"]) for t in tickers if t in prices and prices[t].get("chg_1m") is not None]
    if not pairs: return {}
    pairs.sort(key=lambda x:x[1])
    n=len(pairs)
    return {t:(round(rank/(n-1)*100) if n>1 else 50) for rank,(t,_) in enumerate(pairs)}

def get_rs_stocks():
    global _rs_s,_rs_s_at
    now=datetime.now()
    if not _rs_s or _rs_s_at is None or (now-_rs_s_at).total_seconds()>RS_TTL:
        data=load_watchlists()
        tickers=sorted({t for v in data["themes"].values() for t in v})
        _rs_s=_build_rs(tickers);_rs_s_at=now
        print(f"[rs-stocks] {len(_rs_s)} ranked")
    return _rs_s

def get_rs_etfs():
    global _rs_e,_rs_e_at
    now=datetime.now()
    if not _rs_e or _rs_e_at is None or (now-_rs_e_at).total_seconds()>RS_TTL:
        _rs_e=_build_rs(ETF_TICKERS);_rs_e_at=now
        print(f"[rs-etfs] {len(_rs_e)} ranked")
    return _rs_e

# ── Finviz ─────────────────────────────────────────────────────────────────────
def finviz_peers(ticker):
    try:
        r=requests.get(f"https://finviz.com/quote.ashx?t={ticker}&ty=c&ta=0&p=d",headers=HEADERS,timeout=10)
        if r.status_code!=200: return {"name":ticker,"peers":[],"error":f"HTTP {r.status_code}"}
        soup=BeautifulSoup(r.text,"html.parser")
        nt=soup.find("h2",class_="quote-header_ticker-wrapper_company")
        name=nt.get_text(strip=True) if nt else ticker
        peers=[]
        for td in soup.find_all("td"):
            if td.get_text(strip=True)=="Peers":
                ptd=td.find_next_sibling("td")
                if ptd: peers=[a.get_text(strip=True) for a in ptd.find_all("a") if a.get_text(strip=True)]
                break
        sector=industry=""
        for td in soup.find_all("td"):
            txt=td.get_text(strip=True)
            if txt=="Sector": sector=(td.find_next_sibling("td") or td).get_text(strip=True)
            if txt=="Industry": industry=(td.find_next_sibling("td") or td).get_text(strip=True)
        return {"name":name,"peers":peers,"sector":sector,"industry":industry,"error":None}
    except Exception as e: return {"name":ticker,"peers":[],"error":str(e)}

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index(): return render_template_string(HTML)

@app.route("/api/themes")
def api_themes():
    data=load_watchlists()
    return jsonify({"order":data.get("order",list(data["themes"].keys())),"themes":{k:len(v) for k,v in data["themes"].items()}})

@app.route("/api/watchlist/<path:theme>")
def api_watchlist(theme):
    data=load_watchlists();tickers=data["themes"].get(theme,[])
    if not tickers: return jsonify({"theme":theme,"rows":[],"avg_rs":None})
    prices=fetch_prices(tickers);ext=fetch_ext(tickers);rs_uni=get_rs_stocks()
    rows=[]
    for t in tickers:
        p=prices.get(t,{});ex=ext.get(t,{})
        rows.append({"ticker":t,"price":p.get("price"),"chg_1d":p.get("chg_1d"),"chg_1w":p.get("chg_1w"),"chg_1m":p.get("chg_1m"),"chg_3m":ex.get("chg_3m"),"chg_ytd":ex.get("chg_ytd"),"rs":rs_uni.get(t)})
    rows.sort(key=lambda r:r["chg_1d"] if r["chg_1d"] is not None else -999,reverse=True)
    rs_v=[r["rs"] for r in rows if r["rs"] is not None]
    return jsonify({"theme":theme,"rows":rows,"avg_rs":round(sum(rs_v)/len(rs_v)) if rs_v else None})

@app.route("/api/theme_perf/<path:theme>")
def api_theme_perf(theme):
    data=load_watchlists();tickers=data["themes"].get(theme,[])
    if not tickers: return jsonify({"theme":theme,"avg_1d":None,"avg_1w":None,"avg_1m":None,"avg_rs":None,"count":0,"adv":0,"dec":0})
    prices=fetch_prices(tickers);rs_uni=get_rs_stocks()
    def avg(f): v=[prices[t][f] for t in tickers if t in prices and prices[t].get(f) is not None]; return round(sum(v)/len(v),2) if v else None
    rs_v=[rs_uni[t] for t in tickers if rs_uni.get(t) is not None]
    return jsonify({"theme":theme,"count":len(tickers),"avg_1d":avg("chg_1d"),"avg_1w":avg("chg_1w"),"avg_1m":avg("chg_1m"),"avg_rs":round(sum(rs_v)/len(rs_v)) if rs_v else None,"adv":sum(1 for t in tickers if t in prices and (prices[t].get("chg_1d") or 0)>0),"dec":sum(1 for t in tickers if t in prices and (prices[t].get("chg_1d") or 0)<0)})

@app.route("/api/add_stock",methods=["POST"])
def api_add_stock():
    b=request.get_json();theme=b.get("theme","").strip();tickers=[t.strip().upper() for t in b.get("tickers",[]) if t.strip()]
    if not theme or not tickers: return jsonify({"error":"Missing"}),400
    data=load_watchlists()
    if theme not in data["themes"]: data["themes"][theme]=[]; data["order"].append(theme)
    ex=set(data["themes"][theme]);added=[t for t in tickers if t not in ex]
    data["themes"][theme].extend(added);save_watchlists(data)
    return jsonify({"added":added,"theme":theme})

@app.route("/api/remove_stock",methods=["POST"])
def api_remove_stock():
    b=request.get_json();theme=b.get("theme","").strip();ticker=b.get("ticker","").strip().upper()
    data=load_watchlists()
    if theme in data["themes"] and ticker in data["themes"][theme]:
        data["themes"][theme].remove(ticker);save_watchlists(data)
    return jsonify({"ok":True})

@app.route("/api/add_theme",methods=["POST"])
def api_add_theme():
    theme=request.get_json().get("theme","").strip()
    if not theme: return jsonify({"error":"Empty"}),400
    data=load_watchlists()
    if theme not in data["themes"]: data["themes"][theme]=[]; data["order"].append(theme); save_watchlists(data)
    return jsonify({"ok":True,"theme":theme})

@app.route("/api/peers/<ticker>")
def api_peers(ticker): return jsonify(finviz_peers(ticker.upper()))

@app.route("/api/cleanup",methods=["POST"])
def api_cleanup():
    data=load_watchlists()
    all_tix=list({t for v in data["themes"].values() for t in v})
    if not all_tix: return jsonify({"removed":[],"total_checked":0})
    try:
        import pandas as pd
        raw=yf.download(all_tix,period="5d",interval="1d",auto_adjust=True,progress=False,threads=True)
        cl=raw["Close"] if "Close" in raw.columns else raw.xs("Close",axis=1,level=0)
        if len(all_tix)==1: cl=cl.to_frame(name=all_tix[0])
    except Exception as e: return jsonify({"error":str(e)}),500
    bad={t for t in all_tix if t not in cl.columns or len(cl[t].dropna())==0}
    rm,changed={},False
    for theme,tickers in data["themes"].items():
        before=tickers[:]
        data["themes"][theme]=[t for t in tickers if t not in bad]
        removed=[t for t in before if t in bad]
        if removed: rm[theme]=removed;changed=True
    if changed: save_watchlists(data)
    return jsonify({"removed_map":rm,"total_removed":sum(len(v) for v in rm.values()),"total_checked":len(all_tix)})

@app.route("/api/etf/list")
def api_etf_list():
    rs_uni=get_rs_etfs()
    prices=fetch_prices(ETF_TICKERS);ext=fetch_ext(ETF_TICKERS)
    rows=[]
    for t in ETF_TICKERS:
        p=prices.get(t,{});ex=ext.get(t,{})
        rows.append({"ticker":t,"name":ETF_NAMES.get(t,""),"sector":ETF_SECTOR.get(t,""),"price":p.get("price"),"chg_1d":p.get("chg_1d"),"chg_1w":p.get("chg_1w"),"chg_1m":p.get("chg_1m"),"chg_3m":ex.get("chg_3m"),"chg_ytd":ex.get("chg_ytd"),"rs":rs_uni.get(t)})
    rows.sort(key=lambda r:r["chg_1d"] if r["chg_1d"] is not None else -999,reverse=True)
    rs_v=[r["rs"] for r in rows if r["rs"] is not None]
    return jsonify({"rows":rows,"avg_rs":round(sum(rs_v)/len(rs_v)) if rs_v else None,"count":len(rows)})

@app.route("/api/cache_status")
def api_cache_status(): return jsonify({"date":_cm["date"],"source":_cm["source"],"count":len(_fc),"fresh":_fresh()})

@app.route("/api/cache_reload",methods=["POST"])
def api_cache_reload():
    global _rs_s_at,_rs_e_at
    _load_file_cache();_rs_s_at=None;_rs_e_at=None
    return jsonify({"ok":True,"date":_cm["date"],"count":len(_fc)})

@app.route("/api/refresh_tv",methods=["POST"])
def api_refresh_tv():
    """Fetch prices from TradingView Screener — only stores needed tickers."""
    global _fc,_cm,_rs_s_at,_rs_e_at
    try:
        from tradingview_screener import Query
        _,df=(Query()
            .select('name','close','change','Perf.W','Perf.1M','Perf.3M','Perf.YTD')
            .limit(10000)
            .get_scanner_data())
        wl=load_watchlists()
        needed=set(ETF_TICKERS)|{t for v in wl["themes"].values() for t in v}
        tickers_data={}
        def _f(v):
            try: return round(float(v),2)
            except: return None
        for _,row in df.iterrows():
            t=str(row['name']).split(':')[-1]
            if t not in needed: continue
            tickers_data[t]={"price":_f(row['close']),"chg_1d":_f(row['change']),
                "chg_1w":_f(row.get('Perf.W')),"chg_1m":_f(row.get('Perf.1M')),
                "chg_3m":_f(row.get('Perf.3M')),"chg_ytd":_f(row.get('Perf.YTD'))}
        cache_data={"updated_date":_date.today().isoformat(),"source":"tradingview","tickers":tickers_data}
        payload=json.dumps(cache_data)
        try:
            with open(CACHE_FILE,"w") as f: f.write(payload)
        except: pass
        kv_set("prices_cache",payload)
        _fc=tickers_data;_cm.update(date=cache_data["updated_date"],source="tradingview",loaded_at=datetime.now())
        _rs_s_at=None;_rs_e_at=None
        return jsonify({"ok":True,"count":len(tickers_data),"source":"tradingview","date":cache_data["updated_date"]})
    except Exception as e:
        return jsonify({"error":str(e)}),500

@app.route("/api/upload_cache",methods=["POST"])
def api_upload_cache():
    global _fc,_cm,_rs_s_at,_rs_e_at
    secret=request.headers.get("X-Upload-Secret","")
    if secret!=UPLOAD_SECRET: return jsonify({"error":"Unauthorized"}),401
    try:
        data=request.get_json(force=True)
        tickers_data=data.get("tickers",{})
        if not tickers_data: return jsonify({"error":"Empty tickers"}),400
        cache_data={"updated_date":data.get("updated_date",_date.today().isoformat()),"source":data.get("source","ibkr"),"tickers":tickers_data}
        payload=json.dumps(cache_data)
        try:
            with open(CACHE_FILE,"w") as f: f.write(payload)
        except: pass
        kv_set("prices_cache",payload)
        _fc=tickers_data;_cm.update(date=cache_data["updated_date"],source=cache_data["source"],loaded_at=datetime.now())
        _rs_s_at=None;_rs_e_at=None
        return jsonify({"ok":True,"count":len(tickers_data),"source":cache_data["source"],"date":cache_data["updated_date"]})
    except Exception as e:
        return jsonify({"error":str(e)}),500

@app.route("/api/debug")
def api_debug():
    data=load_watchlists()
    redis_ok=False
    try:
        r=_redis_client(); redis_ok=r is not None and bool(r.ping())
    except: pass
    return jsonify({"is_vercel":IS_VERCEL,"redis_ok":redis_ok,
        "fc_count":len(_fc),"theme_count":len(data.get("themes",{})),
        "cache_date":_cm["date"],"cache_source":_cm["source"]})


# ── HTML ───────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>WATCHLIST BUILDER</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&display=swap" rel="stylesheet"/>
<style>
:root{--bg:#080c12;--bg2:#0c1219;--bg3:#101820;--bg4:#141f2a;--border:#1a2838;--border2:#213040;--amber:#f5a623;--amber-dim:#c47d0e;--amber-glow:rgba(245,166,35,.12);--green:#00e676;--green-dim:#00994d;--red:#ff4d6d;--red-dim:#cc1f40;--blue:#4fc3f7;--blue-bar:#3b82f6;--purple:#b39ddb;--teal:#26c6da;--text:#c8d8e8;--text-dim:#546e8a;--text-muted:#2a3e54;--sw:248px;}
*{margin:0;padding:0;box-sizing:border-box;}html,body{height:100%;}
body{background:var(--bg);color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:12px;display:flex;flex-direction:column;overflow:hidden;}
.topbar{display:flex;align-items:center;padding:0 18px;height:44px;border-bottom:1px solid var(--border);background:var(--bg2);gap:10px;}
.logo-title{font-size:12px;font-weight:600;letter-spacing:.18em;color:var(--amber);}
.tab-group{display:flex;border:1px solid var(--border2);margin-left:6px;}
.tab{background:none;border:none;border-right:1px solid var(--border2);color:var(--text-muted);font-family:inherit;font-size:10px;letter-spacing:.14em;padding:5px 14px;cursor:pointer;}
.tab:last-child{border-right:none;}.tab:hover{color:var(--text);background:var(--bg3);}
.tab.on-s{background:var(--bg4);color:var(--amber);font-weight:600;}
.tab.on-e{background:rgba(38,198,218,.1);color:var(--teal);font-weight:600;}
.tr{margin-left:auto;display:flex;align-items:center;gap:7px;}
.gs{background:var(--bg3);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:11px;padding:5px 10px;width:180px;outline:none;}
.gs:focus{border-color:var(--amber);}.gs::placeholder{color:var(--text-muted);}
.tbtn{background:none;border:1px solid var(--border2);color:var(--text-dim);font-family:inherit;font-size:10px;padding:5px 11px;cursor:pointer;}
.tbtn:hover{border-color:var(--text-dim);color:var(--text);}
.tbtn.am{border-color:var(--amber-dim);color:var(--amber);}.tbtn.am:hover{background:var(--amber-glow);}
.cs{display:flex;align-items:center;gap:5px;border:1px solid var(--border);padding:4px 9px;background:var(--bg3);font-size:10px;color:var(--text-muted);}
.cd{width:6px;height:6px;border-radius:50%;background:var(--text-muted);flex-shrink:0;}
.cd.ok{background:var(--green);box-shadow:0 0 5px var(--green);}.cd.st{background:var(--amber);}.cd.ms{background:var(--red);}
.cb{background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:12px;padding:0 2px;font-family:inherit;}.cb:hover{color:var(--amber);}
.layout{flex:1;display:flex;overflow:hidden;}
.sb{width:var(--sw);min-width:var(--sw);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;background:var(--bg2);}
.sbh{padding:8px 10px;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:5px;flex-shrink:0;}
.sbb{display:none;background:none;border:none;color:var(--amber);font-family:inherit;font-size:10px;cursor:pointer;padding:2px 0;text-align:left;}.sbb:hover{text-decoration:underline;}
.sbs{background:var(--bg3);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:11px;padding:5px 9px;outline:none;width:100%;}.sbs:focus{border-color:var(--amber);}.sbs::placeholder{color:var(--text-muted);}
.ssort{display:flex;border:1px solid var(--border2);}
.ssbtn{flex:1;background:none;border:none;border-right:1px solid var(--border2);color:var(--text-muted);font-family:inherit;font-size:10px;padding:4px 0;cursor:pointer;text-align:center;}
.ssbtn:last-child{border-right:none;}.ssbtn:hover{color:var(--text);background:var(--bg3);}.ssbtn.on{background:var(--bg4);color:var(--amber);font-weight:600;}
.tl{overflow-y:auto;flex:1;}
.ti{display:flex;align-items:center;justify-content:space-between;padding:7px 11px;cursor:pointer;border-bottom:1px solid rgba(26,40,56,.5);gap:5px;}
.ti:hover{background:var(--bg3);}.ti.ac{background:var(--bg4);border-left:2px solid var(--amber);padding-left:9px;}
.ti.ov{background:rgba(59,130,246,.07);border-left:2px solid var(--blue-bar);padding-left:9px;}
.tn{font-size:11px;color:var(--text);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.tb{font-size:10px;flex-shrink:0;}.trs{font-size:9px;flex-shrink:0;margin-left:3px;}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden;}
.ph{display:none;align-items:center;justify-content:space-between;padding:0 16px;height:44px;border-bottom:1px solid var(--border);flex-shrink:0;background:var(--bg2);}
.pt{font-size:12px;font-weight:600;letter-spacing:.14em;}.pm{display:flex;align-items:center;gap:10px;margin-top:1px;}
.ps{font-size:10px;color:var(--text-muted);}
.rsb{font-size:10px;font-weight:600;padding:2px 7px;}
.pa{display:flex;gap:6px;}
.btn{background:none;border:1px solid var(--border2);color:var(--text-dim);font-family:inherit;font-size:10px;padding:5px 11px;cursor:pointer;}.btn:hover{border-color:var(--text-dim);color:var(--text);}
.ba{border-color:var(--blue);color:var(--blue);}.ba:hover{background:rgba(79,195,247,.07);}
.bp2{border-color:var(--purple);color:var(--purple);}.bp2:hover{background:rgba(179,157,219,.07);}
.ss{display:none;border-bottom:1px solid var(--border);background:var(--bg2);flex-shrink:0;}
.si{display:flex;}.sc2{flex:1;padding:5px 12px;border-right:1px solid var(--border);}.sc2:last-child{border-right:none;}
.sl{font-size:9px;color:var(--text-muted);letter-spacing:.1em;}.sv{font-size:12px;font-weight:500;margin-top:1px;}
.pos{color:var(--green);}.neg{color:var(--red);}.neu{color:var(--text-dim);}
.content{flex:1;overflow:hidden;}
.wl-split{display:flex;height:100%;overflow:hidden;}
.wl-left{width:540px;min-width:380px;border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;}
.wl-right{flex:1;display:flex;flex-direction:column;overflow:hidden;background:#000;}
.ch{display:flex;align-items:center;justify-content:space-between;padding:0 14px;height:38px;border-bottom:1px solid var(--border);background:var(--bg2);flex-shrink:0;}
.chl{display:flex;align-items:center;gap:8px;}
.cnav{background:none;border:1px solid var(--border2);color:var(--amber);font-size:16px;line-height:1;padding:2px 8px;cursor:pointer;font-family:inherit;}.cnav:hover{background:var(--amber-glow);}.cnav:disabled{color:var(--text-muted);border-color:var(--border);cursor:default;background:none;}
.chsym{font-size:13px;font-weight:600;letter-spacing:.1em;color:var(--amber);}
.chctr{font-size:10px;color:var(--text-muted);margin-left:6px;}
.chr{display:flex;align-items:center;gap:10px;}
.chl2{font-size:10px;color:var(--text-dim);text-decoration:none;}.chl2:hover{color:var(--amber);}
.cb2{flex:1;overflow:hidden;position:relative;}
.cb2 iframe{width:100%;height:100%;border:none;display:block;}
.ce{display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:11px;letter-spacing:.1em;}
.tw{overflow:auto;flex:1;}
table{width:100%;border-collapse:collapse;}
thead th{position:sticky;top:0;background:var(--bg3);padding:6px 8px;font-size:9px;letter-spacing:.1em;color:var(--text-dim);border-bottom:1px solid var(--border);white-space:nowrap;z-index:2;}
th.r{text-align:right;}th.s{cursor:pointer;}th.s:hover{color:var(--text);}th.as{color:var(--amber);}
tbody tr{border-bottom:1px solid rgba(26,40,56,.55);cursor:pointer;}
tbody tr:hover{background:var(--bg3);}tbody tr.sr{background:rgba(245,166,35,.07);border-left:2px solid var(--amber);}
td{padding:5px 8px;font-size:11px;}
.rk{color:var(--text-muted);font-size:10px;width:24px;}
.tk{font-weight:600;letter-spacing:.08em;color:var(--amber);}
.nm{color:var(--text-dim);font-size:10px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.pr{text-align:right;color:var(--text-dim);}
.rs2{text-align:center;width:36px;}
.rp{display:inline-block;padding:1px 5px;font-size:10px;font-weight:600;min-width:26px;text-align:center;}
.tc{text-align:right;white-space:nowrap;}
.ci{display:flex;align-items:center;justify-content:flex-end;gap:4px;}
.mb{height:5px;border-radius:1px;flex-shrink:0;}
.pv{color:var(--green);}.nv{color:var(--red);}.xv{color:var(--text-muted);}
.rm{background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:12px;padding:0 3px;}.rm:hover{color:var(--red);}
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:200px;color:var(--text-muted);font-size:11px;letter-spacing:.1em;gap:8px;text-align:center;}
.hm3p{background:rgba(0,230,118,.12);}.hm2p{background:rgba(0,230,118,.07);}.hm1p{background:rgba(0,230,118,.03);}
.hm3n{background:rgba(255,77,109,.12);}.hm2n{background:rgba(255,77,109,.07);}.hm1n{background:rgba(255,77,109,.03);}
.perf-wrap{display:flex;flex-direction:column;height:100%;}
.ptb{display:flex;align-items:center;gap:8px;padding:8px 18px;border-bottom:1px solid var(--border);background:var(--bg2);flex-shrink:0;}
.pg{display:flex;border:1px solid var(--border2);}
.pb3{background:none;border:none;border-right:1px solid var(--border2);color:var(--text-muted);font-family:inherit;font-size:10px;padding:4px 11px;cursor:pointer;}.pb3:last-child{border-right:none;}.pb3:hover{color:var(--text);background:var(--bg3);}.pb3.on{background:var(--bg4);color:var(--amber);font-weight:600;}
.pfi{background:var(--bg3);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:11px;padding:4px 9px;outline:none;width:155px;}.pfi:focus{border-color:var(--amber);}.pfi::placeholder{color:var(--text-muted);}
.pin{margin-left:auto;display:flex;align-items:center;gap:8px;font-size:10px;color:var(--text-muted);}
.pr2{background:none;border:1px solid var(--border2);color:var(--text-muted);font-family:inherit;font-size:10px;padding:3px 9px;cursor:pointer;}.pr2:hover{color:var(--amber);border-color:var(--amber-dim);}
.pl{overflow-y:auto;flex:1;}
.pr3{display:grid;grid-template-columns:185px 1fr 44px 60px 68px;align-items:center;height:30px;padding:0 18px;cursor:pointer;border-bottom:1px solid rgba(26,40,56,.35);}
.pr3:hover{background:rgba(59,130,246,.05);}
.pn{font-size:11px;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:8px;}
.pt2{display:grid;grid-template-columns:1fr 1px 1fr;height:10px;background:rgba(255,255,255,.03);}
.ph2{display:flex;align-items:center;}.ph2.l{justify-content:flex-end;}.ph2.r{justify-content:flex-start;}
.pf{height:10px;border-radius:1px;transition:width .45s ease;}.pf.p{background:var(--blue-bar);}.pf.n{background:#d946ef;}
.psep{background:rgba(255,255,255,.12);}
.pad{font-size:9px;color:var(--text-muted);text-align:right;padding-right:6px;}
.prs{font-size:10px;font-weight:600;text-align:center;}
.ppc{font-size:11px;font-weight:500;text-align:right;letter-spacing:.03em;}
.ppc.p{color:#60a5fa;}.ppc.n{color:#d946ef;}.ppc.u{color:var(--text-muted);}
.sk{height:10px;background:linear-gradient(90deg,var(--bg3) 25%,var(--bg4) 50%,var(--bg3) 75%);background-size:200%;animation:sh 1.5s ease infinite;border-radius:1px;width:55%;}
@keyframes sh{0%{background-position:200% 0}100%{background-position:-200% 0}}
.chips{display:flex;flex-wrap:nowrap;overflow-x:auto;gap:4px;padding:5px 18px;border-bottom:1px solid var(--border);background:var(--bg2);flex-shrink:0;scrollbar-width:none;}
.chips::-webkit-scrollbar{display:none;}
.chip{background:none;border:1px solid var(--border2);color:var(--text-muted);font-family:inherit;font-size:9px;padding:2px 8px;cursor:pointer;white-space:nowrap;flex-shrink:0;}
.chip:hover{border-color:var(--text-dim);color:var(--text);}.chip.on{background:var(--bg4);color:var(--amber);border-color:var(--amber-dim);}
.spy-row{background:rgba(59,130,246,.05)!important;border-left:2px solid var(--blue-bar)!important;}
.mo{position:fixed;inset:0;background:rgba(0,0,0,.72);display:none;align-items:center;justify-content:center;z-index:200;backdrop-filter:blur(2px);}.mo.open{display:flex;}
.md{background:var(--bg2);border:1px solid var(--border2);max-width:500px;width:90%;max-height:82vh;display:flex;flex-direction:column;}
.mh{display:flex;align-items:flex-start;justify-content:space-between;padding:13px 17px;border-bottom:1px solid var(--border);}
.mt{font-size:12px;font-weight:600;letter-spacing:.14em;color:var(--amber);}
.ms2{font-size:10px;color:var(--text-muted);margin-top:2px;}
.mx{background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:18px;line-height:1;}.mx:hover{color:var(--red);}
.mb2{padding:15px 17px;overflow-y:auto;flex:1;display:flex;flex-direction:column;gap:11px;}
.mf{padding:11px 17px;border-top:1px solid var(--border);display:flex;gap:7px;}
.fl{font-size:10px;color:var(--text-muted);letter-spacing:.1em;margin-bottom:4px;}
.fi{background:var(--bg3);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:12px;padding:7px 11px;outline:none;width:100%;}.fi:focus{border-color:var(--amber);}.fi::placeholder{color:var(--text-muted);}
.bpri{background:var(--amber);color:var(--bg);font-family:inherit;font-size:11px;font-weight:600;padding:7px 18px;border:none;cursor:pointer;}.bpri:hover{opacity:.85;}
.bsec{background:none;border:1px solid var(--border2);color:var(--text-dim);font-family:inherit;font-size:11px;padding:7px 15px;cursor:pointer;}.bsec:hover{border-color:var(--text-dim);color:var(--text);}
.pg2{display:flex;flex-wrap:wrap;gap:6px;}
.pc2{background:var(--bg3);border:1px solid var(--border);padding:4px 10px;font-size:11px;cursor:pointer;}.pc2:hover{border-color:var(--blue);color:var(--blue);}
.pc2.sel{border-color:var(--green);color:var(--green);background:rgba(0,230,118,.06);}.pc2.used{opacity:.4;cursor:default;}
.ibox{background:var(--bg3);border:1px solid var(--border);padding:8px 12px;font-size:11px;color:var(--text-dim);line-height:1.8;}
.divl{font-size:9px;color:var(--text-muted);letter-spacing:.18em;display:flex;align-items:center;gap:8px;}.divl::before,.divl::after{content:'';flex:1;height:1px;background:var(--border);}
.selact{display:flex;gap:7px;align-items:center;}.selcnt{font-size:10px;color:var(--text-dim);}
.htip{position:fixed;z-index:400;background:var(--bg2);border:1px solid var(--border2);box-shadow:0 8px 40px rgba(0,0,0,.9);padding:8px;pointer-events:none;opacity:0;transition:opacity .15s;width:288px;}
.htip.vis{opacity:1;}.hts{font-size:11px;font-weight:600;color:var(--amber);letter-spacing:.12em;margin-bottom:5px;}
.htip img{display:block;width:272px;height:136px;object-fit:cover;border:1px solid var(--border);}
.hth{font-size:9px;color:var(--text-muted);margin-top:4px;text-align:center;}
@keyframes spin{to{transform:rotate(360deg);}}
::-webkit-scrollbar{width:4px;height:4px;}::-webkit-scrollbar-track{background:var(--bg);}::-webkit-scrollbar-thumb{background:var(--border2);}::-webkit-scrollbar-thumb:hover{background:var(--amber-dim);}
</style>
</head>
<body>
<div class="topbar">
  <span class="logo-title">WATCHLIST BUILDER</span>
  <div class="tab-group">
    <button class="tab on-s" id="tab-s" onclick="switchMode('stocks')">STOCKS</button>
    <button class="tab" id="tab-e" onclick="switchMode('etfs')">ETFs</button>
  </div>
  <div class="tr">
    <div class="cs"><span id="csd" class="cd ms"></span><span id="cst">no cache</span><button class="cb" onclick="reloadCache()">&#8635;</button></div>
    <input class="gs" id="gs" placeholder="Search themes&hellip;" oninput="onGS()"/>
    <button class="tbtn" id="btn-refresh" onclick="refreshTV()">&#9654; REFRESH TV</button>
    <button class="tbtn" id="btn-clean" onclick="runCleanup()">&#9003; CLEAN DEAD</button>
    <button class="tbtn am" id="btn-new" onclick="openNew()">+ NEW THEME</button>
  </div>
</div>
<div class="layout">
  <div id="sidebar" style="width:var(--sw);min-width:var(--sw);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;background:var(--bg2);">
    <div class="sbh">
      <button class="sbb" id="sbb" onclick="showPerf()">&#8592; OVERVIEW</button>
      <input class="sbs" id="sbs" placeholder="Filter themes&hellip;" oninput="onSBS()"/>
      <div class="ssort">
        <button class="ssbtn on" id="ss1d" onclick="setSS('1d')">1D &#9660;</button>
        <button class="ssbtn" id="ss1w" onclick="setSS('1w')">1W</button>
        <button class="ssbtn" id="ss1m" onclick="setSS('1m')">1M</button>
        <button class="ssbtn" id="ssrs" onclick="setSS('rs')">RS</button>
        <button class="ssbtn" id="ssaz" onclick="setSS('az')">A-Z</button>
      </div>
    </div>
    <div class="tl" id="tl"><div class="empty"><div style="width:16px;height:16px;border:2px solid var(--border2);border-top-color:var(--amber);border-radius:50%;animation:spin 1s linear infinite"></div></div></div>
  </div>
  <div class="main">
    <div class="ph" id="ph">
      <div><div class="pt" id="pt">-</div><div class="pm"><span class="ps" id="ps">-</span><span id="prs" class="rsb" style="display:none"></span></div></div>
      <div class="pa"><button class="btn bp2" id="btn-peers" onclick="openPeers()">&#8853; PEERS</button><button class="btn ba" id="btn-add" onclick="openAdd()">+ ADD</button></div>
    </div>
    <div class="ss" id="ss"><div class="si">
      <div class="sc2"><div class="sl">STOCKS</div><div class="sv neu" id="ssn">-</div></div>
      <div class="sc2"><div class="sl">ADV</div><div class="sv pos" id="ssa">-</div></div>
      <div class="sc2"><div class="sl">DEC</div><div class="sv neg" id="ssd">-</div></div>
      <div class="sc2"><div class="sl">BEST 1D</div><div class="sv pos" id="ssb">-</div></div>
      <div class="sc2"><div class="sl">WORST 1D</div><div class="sv neg" id="ssw">-</div></div>
      <div class="sc2"><div class="sl">AVG RS</div><div class="sv neu" id="ssrs2">-</div></div>
    </div></div>
    <div class="content" id="content"><div class="empty">Loading&hellip;</div></div>
  </div>
</div>

<!-- MODALS -->
<div class="mo" id="m-add"><div class="md"><div class="mh"><div><div class="mt">ADD STOCKS</div><div class="ms2" id="m-add-s">-</div></div><button class="mx" onclick="cm('m-add')">&#x2715;</button></div><div class="mb2"><div><div class="fl">TICKERS (space or comma)</div><input class="fi" id="add-inp" placeholder="AAPL NVDA MSFT" autocomplete="off"/></div></div><div class="mf"><button class="bpri" onclick="doAdd()">ADD</button><button class="bsec" onclick="cm('m-add')">CANCEL</button></div></div></div>
<div class="mo" id="m-peers"><div class="md"><div class="mh"><div><div class="mt">PEERS LOOKUP</div><div class="ms2" id="m-peers-s">Finviz</div></div><button class="mx" onclick="cm('m-peers')">&#x2715;</button></div><div class="mb2" id="m-peers-b"><div><div class="fl">SEED TICKER</div><div style="display:flex;gap:7px"><input class="fi" id="peers-inp" placeholder="e.g. NVDA" style="flex:1"/><button class="bpri" onclick="doFetchPeers()" style="padding:7px 13px">FETCH</button></div></div><div id="peers-res"></div></div><div class="mf" id="peers-foot" style="display:none"><div class="selact"><button class="bpri" onclick="doAddPeers()">ADD SELECTED</button><button class="bsec" onclick="selAllPeers()">ALL</button><span class="selcnt" id="sel-cnt">0 selected</span></div></div></div></div>
<div class="mo" id="m-new"><div class="md" style="max-width:400px"><div class="mh"><div><div class="mt">NEW THEME</div></div><button class="mx" onclick="cm('m-new')">&#x2715;</button></div><div class="mb2"><div><div class="fl">THEME NAME</div><input class="fi" id="new-inp" placeholder="e.g. Quantum Computing"/></div></div><div class="mf"><button class="bpri" onclick="doNew()">CREATE</button><button class="bsec" onclick="cm('m-new')">CANCEL</button></div></div></div>

<div id="htip" class="htip"><div class="hts" id="hts"></div><img id="hti" src="" alt=""/><div class="hth">hover preview</div></div>

<script>
// No template literals anywhere in this file - all string concatenation only

var mode='stocks', themeOrder=[], themeCounts={}, activeTheme=null, activeRows=[], sortCol='chg_1d', sortDir=-1;
var sbQ='', sbSort='1d', sbSortDir=-1, perfData={}, perfPeriod='1d', perfQ='', perfLoading=0;
var selTicker=null, selIdx=0;
var etfRows=[], etfSortCol='chg_1d', etfSortDir=-1, etfQ='', etfSectorFilter='ALL';
var etfSelTicker=null, etfSelIdx=0;

function rsColor(v){if(v==null)return'var(--text-muted)';if(v>=80)return'#00e676';if(v>=60)return'#66bb6a';if(v>=40)return'#ffd54f';if(v>=20)return'#ff9800';return'#ff4d6d';}
function rsBg(v){if(v==null)return'transparent';if(v>=80)return'rgba(0,230,118,.12)';if(v>=60)return'rgba(102,187,106,.10)';if(v>=40)return'rgba(255,213,79,.10)';if(v>=20)return'rgba(255,152,0,.10)';return'rgba(255,77,109,.10)';}
function hmCls(v){if(v==null)return'';var a=Math.abs(v);return a>=3?(v>0?'hm3p':'hm3n'):a>=1.5?(v>0?'hm2p':'hm2n'):a>=0.5?(v>0?'hm1p':'hm1n'):'';}
function fmtPct(v){if(v==null)return'<span class="xv">-</span>';return'<span class="'+(v>0?'pv':v<0?'nv':'xv')+'">'+(v>0?'+':'')+v.toFixed(2)+'%</span>';}
function isEtf(){return mode==='etfs';}

// CACHE STATUS
async function fetchCS(){
  try{
    var d=await(await fetch('/api/cache_status')).json();
    var dot=document.getElementById('csd'),txt=document.getElementById('cst');
    if(!d.date){dot.className='cd ms';txt.textContent='no cache';}
    else if(d.fresh){dot.className='cd ok';txt.textContent=d.source+' '+d.date+' '+d.count+'t';}
    else{dot.className='cd st';txt.textContent='stale '+d.date;}
  }catch(e){}
}
async function reloadCache(){
  document.querySelector('.cb').textContent='...';
  await fetch('/api/cache_reload',{method:'POST'});
  await fetchCS();
  document.querySelector('.cb').innerHTML='&#8635;';
  if(isEtf()){loadEtfFlat();}else{perfData={};if(activeTheme)loadTheme(activeTheme);else loadPerfAll();}
}
async function refreshTV(){
  var btn=document.getElementById('btn-refresh'),orig=btn.textContent;
  btn.textContent='FETCHING...';btn.disabled=true;
  try{
    var d=await(await fetch('/api/refresh_tv',{method:'POST'})).json();
    if(d.error){alert('TV Refresh error: '+d.error);return;}
    await fetchCS();
    if(isEtf()){loadEtfFlat();}else{perfData={};if(activeTheme)loadTheme(activeTheme);else loadPerfAll();}
    btn.textContent='OK '+d.count+'t';
  }catch(e){alert(e.message);}
  setTimeout(function(){btn.textContent=orig;btn.disabled=false;},3000);
}

// BOOT
async function boot(){
  fetchCS();
  document.getElementById('btn-clean').style.display='';
  document.getElementById('btn-new').style.display='';
  var d=await(await fetch('/api/themes')).json();
  themeOrder=d.order; themeCounts=d.themes;
  renderSidebar(); showPerf();
}

// MODE SWITCH
function switchMode(m){
  if(m===mode)return;
  mode=m; activeTheme=null; perfData={}; themeOrder=[]; themeCounts={}; selTicker=null; sbQ='';
  document.getElementById('sbs').value=''; document.getElementById('gs').value='';
  document.getElementById('tab-s').className='tab'+(m==='stocks'?' on-s':'');
  document.getElementById('tab-e').className='tab'+(m==='etfs'?' on-e':'');
  var stockOnly=m==='stocks';
  document.getElementById('btn-clean').style.display=stockOnly?'':'none';
  document.getElementById('btn-new').style.display=stockOnly?'':'none';
  document.getElementById('ph').style.display='none';
  document.getElementById('ss').style.display='none';
  document.getElementById('sbb').style.display='none';
  if(isEtf()){
    document.getElementById('sidebar').style.display='none';
    loadEtfFlat();
  }else{
    document.getElementById('sidebar').style.display='flex';
    document.getElementById('content').innerHTML='<div class="empty"><div style="width:16px;height:16px;border:2px solid var(--border2);border-top-color:var(--amber);border-radius:50%;animation:spin 1s linear infinite"></div></div>';
    fetch('/api/themes').then(function(r){return r.json();}).then(function(d){themeOrder=d.order;themeCounts=d.themes;renderSidebar();showPerf();});
  }
}

// SIDEBAR SORT
function setSS(s){
  // Toggle direction if clicking same button, else reset to descending
  if(s!=='az'){
    sbSortDir = (sbSort===s) ? -sbSortDir : -1;
  } else {
    sbSortDir = 1;
  }
  sbSort=s;
  // Update button labels with arrow indicator
  ['1d','1w','1m','rs','az'].forEach(function(k){
    var el=document.getElementById('ss'+k);
    var isOn=s===k;
    el.className='ssbtn'+(isOn?' on':'');
    if(isOn&&k!=='az'){
      el.textContent=k.toUpperCase()+(sbSortDir===-1?' ▼':' ▲');
    } else {
      el.textContent=k.toUpperCase();
    }
  });
  if(s==='1d'||s==='1w'||s==='1m'){perfPeriod=s;document.querySelectorAll('.pb3').forEach(function(b){b.classList.toggle('on',b.dataset.p===s);});if(!activeTheme)renderPerfChart();}
  renderSidebar();
}
function onSBS(){sbQ=document.getElementById('sbs').value.toLowerCase();renderSidebar();}
function onGS(){sbQ=document.getElementById('gs').value.toLowerCase();document.getElementById('sbs').value=sbQ;renderSidebar();}

function renderSidebar(){
  var el=document.getElementById('tl');
  var field=sbSort==='1d'?'avg_1d':sbSort==='1w'?'avg_1w':sbSort==='1m'?'avg_1m':null;
  var items=themeOrder.filter(function(t){return !sbQ||t.toLowerCase().indexOf(sbQ)>=0;});
  items=items.slice().sort(function(a,b){
    if(sbSort==='az')return a.localeCompare(b);
    var pa=perfData[a],pb=perfData[b];
    var av,bv;
    if(sbSort==='rs'){av=pa?pa.avg_rs:null;bv=pb?pb.avg_rs:null;}
    else{av=pa?pa[field]:null;bv=pb?pb[field]:null;}
    if(av==null&&bv==null)return 0;if(av==null)return 1;if(bv==null)return-1;
    return sbSortDir*(bv-av);
  });
  if(!items.length){el.innerHTML='<div class="empty" style="min-height:80px;font-size:10px">NO MATCHES</div>';return;}
  var h='';
  items.forEach(function(t){
    var cls=t===activeTheme?'ti ac':activeTheme===null?'ti ov':'ti';
    var pd=perfData[t],pv=pd&&field?pd[field]:null,rs=pd?pd.avg_rs:null;
    var badge,rsTxt='';
    if(sbSort==='rs'&&rs!=null){badge='<span class="tb" style="color:'+rsColor(rs)+';font-weight:600">RS'+rs+'</span>';}
    else if(pv!=null){badge='<span class="tb" style="color:'+(pv>=0?'#60a5fa':'#d946ef')+'">'+(pv>=0?'+':'')+pv.toFixed(2)+'%</span>';}
    else{badge='<span class="tb" style="color:var(--text-muted)">'+(themeCounts[t]||0)+'</span>';}
    if(sbSort!=='rs'&&rs!=null){rsTxt='<span class="trs" style="color:'+rsColor(rs)+'">RS'+rs+'</span>';}
    h+='<div class="'+cls+'" onclick="loadTheme(this.dataset.t)" data-t="'+t+'">'
      +'<span class="tn">'+t+'</span>'+rsTxt+badge+'</div>';
  });
  el.innerHTML=h;
}

// PERF OVERVIEW
function showPerf(){
  activeTheme=null;
  document.getElementById('ph').style.display='none';
  document.getElementById('ss').style.display='none';
  document.getElementById('sbb').style.display='none';
  renderSidebar(); renderPerfChart();
  if(!Object.keys(perfData).length)loadPerfAll();
}

async function loadPerfAll(){
  perfData={}; perfLoading=themeOrder.length; renderPerfChart();
  await Promise.allSettled(themeOrder.map(function(theme){
    return fetch('/api/theme_perf/'+encodeURIComponent(theme))
      .then(function(r){return r.json();})
      .then(function(d){
        perfData[d.theme]={avg_1d:d.avg_1d,avg_1w:d.avg_1w,avg_1m:d.avg_1m,avg_rs:d.avg_rs,adv:d.adv,dec:d.dec};
        perfLoading=Math.max(0,perfLoading-1);
        if(!activeTheme)renderPerfChart(); renderSidebar();
      }).catch(function(){perfLoading=Math.max(0,perfLoading-1);});
  }));
}

function setPeriod(p){
  perfPeriod=p;
  document.querySelectorAll('.pb3').forEach(function(b){b.classList.toggle('on',b.dataset.p===p);});
  if(sbSort==='1d'||sbSort==='1w'||sbSort==='1m'){sbSort=p;['1d','1w','1m','rs','az'].forEach(function(k){document.getElementById('ss'+k).className='sb'+(p===k?' on':'');});}
  renderPerfChart(); renderSidebar();
}
function onPQ(){perfQ=document.getElementById('pf').value.toLowerCase();renderPerfChart();}

function renderPerfChart(){
  var area=document.getElementById('content');
  var field=perfPeriod==='1d'?'avg_1d':perfPeriod==='1w'?'avg_1w':'avg_1m';
  var sf=sbSort==='rs'?'avg_rs':field;
  var nL=Object.keys(perfData).length,nT=themeOrder.length;
  var rows=themeOrder.filter(function(t){return !perfQ||t.toLowerCase().indexOf(perfQ)>=0;})
    .map(function(t){var o=perfData[t]||{};return{theme:t,avg_1d:o.avg_1d,avg_1w:o.avg_1w,avg_1m:o.avg_1m,avg_rs:o.avg_rs,adv:o.adv,dec:o.dec,ok:!!perfData[t]};})
    .sort(function(a,b){
      if(!a.ok&&!b.ok)return 0;if(!a.ok)return 1;if(!b.ok)return-1;
      var av=a[sf],bv=b[sf];if(av==null&&bv==null)return 0;if(av==null)return 1;if(bv==null)return-1;return bv-av;
    });
  var mx=rows.reduce(function(m,r){return Math.max(m,Math.abs(r[field]||0));},0.001);
  var spin=perfLoading>0?('<span style="display:inline-block;animation:spin 1s linear infinite">&#8635;</span> '+nL+'/'+nT):('&#10003; '+nL+'/'+nT);
  var h='<div class="perf-wrap"><div class="ptb">'
    +'<div class="pg">'
    +'<button class="pb3'+(perfPeriod==='1d'?' on':'')+'" data-p="1d" onclick="setPeriod(\'1d\')">TODAY</button>'
    +'<button class="pb3'+(perfPeriod==='1w'?' on':'')+'" data-p="1w" onclick="setPeriod(\'1w\')">1W</button>'
    +'<button class="pb3'+(perfPeriod==='1m'?' on':'')+'" data-p="1m" onclick="setPeriod(\'1m\')">1M</button>'
    +'</div>'
    +'<input class="pfi" id="pf" value="'+perfQ+'" placeholder="Filter themes&hellip;" oninput="onPQ()"/>'
    +'<div class="pin">'+spin+'<button class="pr2" onclick="perfData={};loadPerfAll()">&#8635; REFRESH</button></div>'
    +'</div><div class="pl">';
  rows.forEach(function(r){
    var val=r[field];
    if(!r.ok){h+='<div class="pr3"><span class="pn" style="color:var(--text-muted)">'+r.theme+'</span><div class="pt2"><div class="ph2 l"></div><div class="psep"></div><div class="ph2 r"><div class="sk"></div></div></div><span class="prs"></span><span class="pad"></span><span class="ppc u">&hellip;</span></div>';return;}
    var pct=val!=null?val:0,isP=pct>=0,fw=Math.min(Math.abs(pct)/mx*100,100);
    var ps=val!=null?(isP?'+':'')+val.toFixed(2)+'%':'--';
    var pc=val==null?'u':isP?'p':'n';
    var adv=r.adv!=null?('<span style="color:#60a5fa">'+r.adv+'&#8593;</span> <span style="color:#d946ef">'+r.dec+'&#8595;</span>'):'';
    var rsHl=sbSort==='rs';
    var rsH=r.avg_rs!=null?('<span style="color:'+rsColor(r.avg_rs)+';font-size:'+(rsHl?'11':'10')+'px;font-weight:600;'+(rsHl?'background:'+rsBg(r.avg_rs)+';padding:1px 5px;border-radius:2px':'')+'">'+(r.avg_rs)+'</span>'):'<span style="color:var(--text-muted);font-size:10px">-</span>';
    h+='<div class="pr3" onclick="loadTheme(\''+r.theme.replace(/'/g,"\\'")+'\')">'
      +'<span class="pn">'+r.theme+'</span>'
      +'<div class="pt2"><div class="ph2 l">'+(isP?'':'<div class="pf n" style="width:'+fw+'%"></div>')+'</div><div class="psep"></div><div class="ph2 r">'+(isP?'<div class="pf p" style="width:'+fw+'%"></div>':'')+'</div></div>'
      +'<span class="prs">'+rsH+'</span>'
      +'<span class="pad">'+adv+'</span>'
      +'<span class="ppc '+pc+'">'+ps+'</span>'
      +'</div>';
  });
  area.innerHTML=h+'</div></div>';
}

// STOCK WATCHLIST
function sort2(rows){
  return rows.slice().sort(function(a,b){
    var av=a[sortCol],bv=b[sortCol];
    if(sortCol==='ticker'){av=av||'';bv=bv||'';return sortDir*av.localeCompare(bv);}
    if(av==null&&bv==null)return 0;if(av==null)return 1;if(bv==null)return-1;
    return sortDir*(bv-av);
  });
}
function setSort(c){sortDir=sortCol===c?-sortDir:(c==='ticker'?1:-1);sortCol=c;renderTable();}

async function loadTheme(name){
  activeTheme=name; selTicker=null; selIdx=0;
  renderSidebar();
  document.getElementById('ph').style.display='flex';
  document.getElementById('ss').style.display='block';
  document.getElementById('sbb').style.display='block';
  document.getElementById('pt').textContent=name.toUpperCase();
  document.getElementById('ps').textContent=(themeCounts[name]||0)+' stocks';
  document.getElementById('prs').style.display='none';
  document.getElementById('m-add-s').textContent='-> '+name;
  document.getElementById('m-peers-s').textContent='-> '+name;
  document.getElementById('btn-peers').style.display='';
  document.getElementById('btn-add').style.display='';
  var area=document.getElementById('content');
  area.innerHTML='<div class="empty"><div style="width:16px;height:16px;border:2px solid var(--border2);border-top-color:var(--amber);border-radius:50%;animation:spin 1s linear infinite"></div></div>';
  var d=await(await fetch('/api/watchlist/'+encodeURIComponent(name))).json();
  activeRows=d.rows; updateStrip(d.avg_rs); renderWLSplit();
  if(activeRows.length){var rs=sort2(activeRows);selRow(rs[0].ticker,0);}
}

function renderWLSplit(){
  var area=document.getElementById('content');
  area.innerHTML='<div class="wl-split">'
    +'<div class="wl-left"><div class="tw" id="wltw"></div></div>'
    +'<div class="wl-right">'
    +'<div class="ch"><div class="chl">'
    +'<button class="cnav" id="ch-prev" onclick="slideRow(-1)">&#8249;</button>'
    +'<div><span class="chsym" id="ch-sym">-</span><span class="chctr" id="ch-ctr"></span></div>'
    +'<button class="cnav" id="ch-next" onclick="slideRow(1)">&#8250;</button>'
    +'</div><div class="chr">'
    +'<a class="chl2" id="ch-tv" href="#" target="_blank">&#8599; TV</a>'
    +'<a class="chl2" id="ch-fv" href="#" target="_blank">&#8599; FV</a>'
    +'</div></div>'
    +'<div class="cb2"><div class="ce" id="ch-empty">&#8592; SELECT A TICKER</div>'
    +'<iframe id="ch-ifr" src="" allowfullscreen style="display:none"></iframe>'
    +'</div></div></div>';
  renderTable();
}

function renderTable(){
  var wrap=document.getElementById('wltw'); if(!wrap)return;
  var rows=sort2(activeRows);
  if(!rows.length){wrap.innerHTML='<div class="empty">Empty watchlist.</div>';return;}
  var mx=rows.reduce(function(m,r){return Math.max(m,Math.abs(r.chg_1d||0));},0.01);
  function A(c){return c===sortCol?(sortDir===-1?' &#9660;':' &#9650;'):'';}
  function C(c){return c===sortCol?' as':'';}
  var h='<table><thead><tr>'
    +'<th style="width:24px">#</th>'
    +'<th class="s'+C('ticker')+'" onclick="setSort(\'ticker\')">TICKER'+A('ticker')+'</th>'
    +'<th class="r s'+C('price')+'" onclick="setSort(\'price\')">PRICE'+A('price')+'</th>'
    +'<th class="r s'+C('rs')+'" onclick="setSort(\'rs\')" title="RS 0-100 within universe">RS'+A('rs')+'</th>'
    +'<th class="r s'+C('chg_1d')+'" onclick="setSort(\'chg_1d\')">1D'+A('chg_1d')+'</th>'
    +'<th class="r s'+C('chg_1w')+'" onclick="setSort(\'chg_1w\')">1W'+A('chg_1w')+'</th>'
    +'<th class="r s'+C('chg_1m')+'" onclick="setSort(\'chg_1m\')">1M'+A('chg_1m')+'</th>'
    +'<th class="r s'+C('chg_3m')+'" onclick="setSort(\'chg_3m\')">3M'+A('chg_3m')+'</th>'
    +'<th class="r s'+C('chg_ytd')+'" onclick="setSort(\'chg_ytd\')">YTD'+A('chg_ytd')+'</th>'
    +'<th></th></tr></thead><tbody>';
  rows.forEach(function(r,i){
    var p=r.price!=null?'$'+r.price.toFixed(2):'-';
    var rsp=r.rs!=null?'<div class="rp" style="color:'+rsColor(r.rs)+';background:'+rsBg(r.rs)+'">'+r.rs+'</div>':'<span class="xv">-</span>';
    var isSel=r.ticker===selTicker?' sr':'';
    var bw=r.chg_1d!=null?Math.min(Math.abs(r.chg_1d)/mx*36,36):0;
    var bc=r.chg_1d!=null&&r.chg_1d>=0?'var(--green-dim)':'var(--red-dim)';
    var mb=r.chg_1d!=null?'<div class="mb" style="width:'+bw+'px;background:'+bc+'"></div>':'';
    h+='<tr class="'+isSel+'" onclick="selRow(\''+r.ticker+'\','+i+')">'
      +'<td class="rk">'+(i+1)+'</td>'
      +'<td class="tk" onmouseenter="showHtip(\''+r.ticker+'\',event)" onmouseleave="hideHtip()">'+r.ticker+'</td>'
      +'<td class="pr">'+p+'</td>'
      +'<td class="rs2">'+rsp+'</td>'
      +'<td class="tc '+hmCls(r.chg_1d)+'"><div class="ci">'+mb+fmtPct(r.chg_1d)+'</div></td>'
      +'<td class="tc '+hmCls(r.chg_1w)+'">'+fmtPct(r.chg_1w)+'</td>'
      +'<td class="tc '+hmCls(r.chg_1m)+'">'+fmtPct(r.chg_1m)+'</td>'
      +'<td class="tc '+hmCls(r.chg_3m)+'">'+fmtPct(r.chg_3m)+'</td>'
      +'<td class="tc '+hmCls(r.chg_ytd)+'">'+fmtPct(r.chg_ytd)+'</td>'
      +'<td><button class="rm" onclick="event.stopPropagation();rmStock(\''+r.ticker+'\')">&#x2715;</button></td>'
      +'</tr>';
  });
  wrap.innerHTML=h+'</tbody></table>';
}

function updateStrip(avgRs){
  var rows=activeRows,valid=rows.filter(function(r){return r.chg_1d!=null;});
  document.getElementById('ssn').textContent=rows.length;
  document.getElementById('ssa').textContent=rows.filter(function(r){return(r.chg_1d||0)>0;}).length;
  document.getElementById('ssd').textContent=rows.filter(function(r){return(r.chg_1d||0)<0;}).length;
  var best=valid.length?valid.reduce(function(a,b){return a.chg_1d>b.chg_1d?a:b;}):null;
  var worst=valid.length?valid.reduce(function(a,b){return a.chg_1d<b.chg_1d?a:b;}):null;
  document.getElementById('ssb').textContent=best?best.ticker+' +'+(best.chg_1d.toFixed(2))+'%':'-';
  document.getElementById('ssw').textContent=worst?worst.ticker+' '+(worst.chg_1d.toFixed(2))+'%':'-';
  var rsEl=document.getElementById('ssrs2');
  if(avgRs!=null){rsEl.textContent=avgRs;rsEl.style.color=rsColor(avgRs);}else{rsEl.textContent='-';rsEl.style.color='';}
  document.getElementById('ps').textContent=rows.length+' stocks';
  themeCounts[activeTheme]=rows.length; renderSidebar();
  var badge=document.getElementById('prs');
  if(avgRs!=null){badge.textContent='RS '+avgRs;badge.style.color=rsColor(avgRs);badge.style.background=rsBg(avgRs);badge.style.display='inline';}
  else badge.style.display='none';
}

function selRow(ticker,idx){
  selTicker=ticker; selIdx=idx; renderTable(); drawChart(ticker,idx);
}
function slideRow(dir){
  var rows=sort2(activeRows),ni=selIdx+dir;
  if(ni<0||ni>=rows.length)return; selRow(rows[ni].ticker,ni);
}
function drawChart(ticker,idx){
  var rows=sort2(activeRows);
  var sym=document.getElementById('ch-sym'); if(!sym)return;
  sym.textContent=ticker;
  document.getElementById('ch-ctr').textContent=(idx+1)+' / '+rows.length;
  document.getElementById('ch-prev').disabled=idx<=0;
  document.getElementById('ch-next').disabled=idx>=rows.length-1;
  document.getElementById('ch-tv').href='https://www.tradingview.com/chart/?symbol='+ticker;
  document.getElementById('ch-fv').href='https://finviz.com/quote.ashx?t='+ticker;
  var empty=document.getElementById('ch-empty'),ifr=document.getElementById('ch-ifr');
  if(empty)empty.style.display='none'; ifr.style.display='block';
  var st='EMA%40tv-basicstudies%7CEMA%40tv-basicstudies%7CMASimple%40tv-basicstudies%7CMASimple%40tv-basicstudies';
  ifr.src='https://www.tradingview.com/widgetembed/?frameElementId=tv_s'
    +'&symbol='+encodeURIComponent(ticker)+'&interval=D&theme=dark&style=1'
    +'&toolbarbg=000000&withdateranges=1&locale=en&hidesidetoolbar=0'
    +'&studies='+st;
}

async function rmStock(t){
  await fetch('/api/remove_stock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({theme:activeTheme,ticker:t})});
  activeRows=activeRows.filter(function(r){return r.ticker!==t;});
  if(selTicker===t){selTicker=null;var i=document.getElementById('ch-ifr'),e=document.getElementById('ch-empty');if(i)i.style.display='none';if(e)e.style.display='flex';}
  renderTable(); updateStrip(null);
}

// ADD / PEERS / NEW
function openAdd(){document.getElementById('add-inp').value='';om('m-add');setTimeout(function(){document.getElementById('add-inp').focus();},80);}
async function doAdd(){
  var tix=document.getElementById('add-inp').value.replace(/,/g,' ').split(' ').map(function(t){return t.trim().toUpperCase();}).filter(Boolean);
  if(!tix.length)return;
  await fetch('/api/add_stock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({theme:activeTheme,tickers:tix})});
  cm('m-add'); loadTheme(activeTheme);
}
var selPeers=new Set(),existPeers=new Set();
function openPeers(){document.getElementById('peers-inp').value='';document.getElementById('peers-res').innerHTML='';document.getElementById('peers-foot').style.display='none';selPeers=new Set();existPeers=new Set(activeRows.map(function(r){return r.ticker;}));om('m-peers');setTimeout(function(){document.getElementById('peers-inp').focus();},80);}
async function doFetchPeers(){
  var t=document.getElementById('peers-inp').value.trim().toUpperCase();if(!t)return;
  var res=document.getElementById('peers-res');
  res.innerHTML='<div style="color:var(--text-dim);font-size:11px;padding:8px 0">Fetching...</div>';
  document.getElementById('peers-foot').style.display='none';
  try{
    var d=await(await fetch('/api/peers/'+t)).json();
    if(d.error){res.innerHTML='<div style="color:var(--red);font-size:11px">Error: '+d.error+'</div>';return;}
    var all=[t].concat(d.peers).filter(function(v,i,a){return a.indexOf(v)===i;});
    selPeers=new Set(all.filter(function(p){return !existPeers.has(p);}));
    var html='<div class="ibox">'+t+' - '+(d.name||'')+'<span style="color:var(--text-muted)"> '+d.sector+'</span></div>'
      +'<div class="divl">PEERS ('+d.peers.length+')</div><div class="pg2" id="pg2">';
    all.forEach(function(p){var u=existPeers.has(p),s=selPeers.has(p);html+='<div class="pc2 '+(u?'used':s?'sel':'')+'" data-t="'+p+'" onclick="togPeer(\''+p+'\')">'+p+'</div>';});
    res.innerHTML=html+'</div>';
    document.getElementById('peers-foot').style.display='flex'; upSelCnt();
  }catch(e){res.innerHTML='<div style="color:var(--red);font-size:11px">Error: '+e.message+'</div>';}
}
function togPeer(t){if(existPeers.has(t))return;selPeers.has(t)?selPeers.delete(t):selPeers.add(t);var el=document.querySelector('.pc2[data-t="'+t+'"]');if(el)el.classList.toggle('sel',selPeers.has(t));upSelCnt();}
function selAllPeers(){document.querySelectorAll('.pc2:not(.used)').forEach(function(c){selPeers.add(c.dataset.t);c.classList.add('sel');});upSelCnt();}
function upSelCnt(){document.getElementById('sel-cnt').textContent=selPeers.size+' selected';}
async function doAddPeers(){if(!selPeers.size)return;await fetch('/api/add_stock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({theme:activeTheme,tickers:Array.from(selPeers)})});cm('m-peers');loadTheme(activeTheme);}
function openNew(){document.getElementById('new-inp').value='';om('m-new');setTimeout(function(){document.getElementById('new-inp').focus();},80);}
async function doNew(){
  var name=document.getElementById('new-inp').value.trim();if(!name)return;
  var d=await(await fetch('/api/add_theme',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({theme:name})})).json();
  cm('m-new');if(!d.error){themeOrder.push(name);themeCounts[name]=0;renderSidebar();loadTheme(name);}
}

// ETF FLAT VIEW
var ALL_SECTORS=['Market','Tech','Semi','Energy','Oil','Nat Gas','Telecom','Cmdty','Agri','Gold','Silver','Metals','Uranium','Clean','Biotech','Health','Finance','RE','Cons D','Cons S','Indus','Trans','Infra','Comm','Util','Matrl','Build','China','Intl','Bonds','Robo','ARK','EV','Crypto','Cannabis','Gaming','Cyber','Space','Quantum','Social','Fintech','Water','Timber','Enviro','Factor','Dollar','Ship','IPO'];
var SC={'Market':'#60a5fa','Tech':'#a78bfa','Semi':'#818cf8','Energy':'#fb923c','Oil':'#f97316','Nat Gas':'#fbbf24','Telecom':'#34d399','Cmdty':'#d97706','Agri':'#86efac','Gold':'#fcd34d','Silver':'#94a3b8','Metals':'#6b7280','Uranium':'#22d3ee','Clean':'#4ade80','Biotech':'#f472b6','Health':'#fb7185','Finance':'#38bdf8','RE':'#a3e635','Cons D':'#c084fc','Cons S':'#86efac','Indus':'#64748b','Trans':'#475569','Infra':'#0ea5e9','Comm':'#e879f9','Util':'#fde68a','Matrl':'#d4d4d8','Build':'#fca5a5','China':'#f87171','Intl':'#6ee7b7','Bonds':'#93c5fd','Robo':'#c4b5fd','ARK':'#f9a8d4','EV':'#86efac','Crypto':'#fbbf24','Cannabis':'#4ade80','Gaming':'#f472b6','Cyber':'#22d3ee','Space':'#818cf8','Quantum':'#a78bfa','Social':'#60a5fa','Fintech':'#34d399','Water':'#38bdf8','Timber':'#86efac','Enviro':'#4ade80','Factor':'#94a3b8','Dollar':'#fcd34d','Ship':'#64748b','IPO':'#f9a8d4'};

function setEtfSector(s){
  etfSectorFilter=s;
  document.querySelectorAll('.chip').forEach(function(c){c.classList.toggle('on',c.dataset.s===s);});
  renderEtfTable();
}
function setEtfSort(c){etfSortDir=etfSortCol===c?-etfSortDir:-1;etfSortCol=c;renderEtfTable();}
function setEtfPeriod(p){etfSortCol='chg_'+p;etfSortDir=-1;document.querySelectorAll('.epb').forEach(function(b){b.classList.toggle('on',b.dataset.p===p);});renderEtfTable();}
function onEtfQ(){etfQ=document.getElementById('etf-search').value.toLowerCase();renderEtfTable();}

async function loadEtfFlat(){
  var area=document.getElementById('content');
  area.innerHTML='<div class="empty"><div style="width:16px;height:16px;border:2px solid var(--border2);border-top-color:var(--teal);border-radius:50%;animation:spin 1s linear infinite"></div></div>';
  var d=await(await fetch('/api/etf/list')).json();
  etfRows=d.rows;
  renderEtfView();
}

function renderEtfView(){
  var area=document.getElementById('content');
  var chips='<div class="chips"><button class="chip on" data-s="ALL" onclick="setEtfSector(\'ALL\')">ALL</button>';
  ALL_SECTORS.forEach(function(s){chips+='<button class="chip" data-s="'+s+'" onclick="setEtfSector(\''+s+'\')">'+s+'</button>';});
  chips+='</div>';
  area.innerHTML='<div style="display:flex;height:100%;overflow:hidden;">'
    +'<div style="flex:1;display:flex;flex-direction:column;overflow:hidden;">'
    +'<div style="display:flex;align-items:center;gap:8px;padding:8px 18px;border-bottom:1px solid var(--border);background:var(--bg2);flex-shrink:0;">'
    +'<div class="pg">'
    +'<button class="pb3 epb on" data-p="1d" onclick="setEtfPeriod(\'1d\')">TODAY</button>'
    +'<button class="pb3 epb" data-p="1w" onclick="setEtfPeriod(\'1w\')">1W</button>'
    +'<button class="pb3 epb" data-p="1m" onclick="setEtfPeriod(\'1m\')">1M</button>'
    +'<button class="pb3" onclick="setEtfSort(\'rs\')">RS</button>'
    +'</div>'
    +'<input style="background:var(--bg3);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:11px;padding:4px 9px;outline:none;width:180px;" id="etf-search" placeholder="Filter ETFs&hellip;" oninput="onEtfQ()"/>'
    +'<span style="margin-left:auto;font-size:10px;color:var(--text-muted)">'+etfRows.length+' ETFs &middot; RS within ETF universe &middot; &#8593;&#8595; to navigate</span>'
    +'</div>'
    +chips
    +'<div class="tw" id="etf-tw" style="flex:1;overflow:auto;"></div>'
    +'</div>'
    +'<div style="width:500px;min-width:380px;border-left:1px solid var(--border);display:flex;flex-direction:column;background:#000;">'
    +'<div class="ch"><div class="chl">'
    +'<button class="cnav" id="etf-prev" onclick="slideEtf(-1)">&#8249;</button>'
    +'<div><span class="chsym" id="etf-sym" style="color:var(--teal)">-</span><span class="chctr" id="etf-ctr"></span></div>'
    +'<button class="cnav" id="etf-next" onclick="slideEtf(1)">&#8250;</button>'
    +'</div><div class="chr">'
    +'<a class="chl2" id="etf-tv" href="#" target="_blank">&#8599; TV</a>'
    +'<a class="chl2" id="etf-fv" href="#" target="_blank">&#8599; FV</a>'
    +'</div></div>'
    +'<div class="cb2"><div class="ce" id="etf-empty">&#8592; SELECT AN ETF</div>'
    +'<iframe id="etf-ifr" src="" allowfullscreen style="display:none"></iframe>'
    +'</div></div></div>';
  renderEtfTable();
  if(etfRows.length)selEtf(etfRows[0].ticker,0);
}

function etfSort2(rows){
  return rows.slice().sort(function(a,b){
    var av=a[etfSortCol],bv=b[etfSortCol];
    if(etfSortCol==='ticker'||etfSortCol==='sector'||etfSortCol==='name'){av=av||'';bv=bv||'';return etfSortDir*av.localeCompare(bv);}
    if(av==null&&bv==null)return 0;if(av==null)return 1;if(bv==null)return-1;return etfSortDir*(bv-av);
  });
}

function renderEtfTable(){
  var wrap=document.getElementById('etf-tw');if(!wrap)return;
  var filtered=etfRows.filter(function(r){
    var q=!etfQ||(r.ticker+r.name+r.sector).toLowerCase().indexOf(etfQ)>=0;
    var s=etfSectorFilter==='ALL'||r.sector===etfSectorFilter;
    return q&&s;
  });
  var rows=etfSort2(filtered);
  if(!rows.length){wrap.innerHTML='<div class="empty">No ETFs match.</div>';return;}
  var mx=rows.reduce(function(m,r){return Math.max(m,Math.abs(r.chg_1d||0));},0.01);
  function A(c){return c===etfSortCol?(etfSortDir===-1?' &#9660;':' &#9650;'):'';}
  function C(c){return c===etfSortCol?' as':'';}
  // Pin SPY
  var spyRow=filtered.find(function(r){return r.ticker==='SPY';});
  var mainRows=etfSortCol==='chg_1d'&&!etfQ&&etfSectorFilter==='ALL'&&spyRow?rows.filter(function(r){return r.ticker!=='SPY';}):rows;
  var h='<table><thead><tr>'
    +'<th style="width:24px">#</th>'
    +'<th class="s'+C('ticker')+'" onclick="setEtfSort(\'ticker\')">TICKER'+A('ticker')+'</th>'
    +'<th class="s'+C('sector')+'" onclick="setEtfSort(\'sector\')">SECTOR'+A('sector')+'</th>'
    +'<th class="s'+C('name')+'" onclick="setEtfSort(\'name\')">NAME'+A('name')+'</th>'
    +'<th class="r s'+C('price')+'" onclick="setEtfSort(\'price\')">PRICE'+A('price')+'</th>'
    +'<th class="r s'+C('rs')+'" onclick="setEtfSort(\'rs\')" title="RS 0-100">RS'+A('rs')+'</th>'
    +'<th class="r s'+C('chg_1d')+'" onclick="setEtfSort(\'chg_1d\')">1D'+A('chg_1d')+'</th>'
    +'<th class="r s'+C('chg_1w')+'" onclick="setEtfSort(\'chg_1w\')">1W'+A('chg_1w')+'</th>'
    +'<th class="r s'+C('chg_1m')+'" onclick="setEtfSort(\'chg_1m\')">1M'+A('chg_1m')+'</th>'
    +'<th class="r s'+C('chg_3m')+'" onclick="setEtfSort(\'chg_3m\')">3M'+A('chg_3m')+'</th>'
    +'<th class="r s'+C('chg_ytd')+'" onclick="setEtfSort(\'chg_ytd\')">YTD'+A('chg_ytd')+'</th>'
    +'</tr></thead><tbody>';
  function makeEtfRow(r,i,isSpy){
    var p=r.price!=null?'$'+r.price.toFixed(2):'-';
    var rsp=r.rs!=null?'<div class="rp" style="color:'+rsColor(r.rs)+';background:'+rsBg(r.rs)+'">'+r.rs+'</div>':'<span class="xv">-</span>';
    var sc=SC[r.sector]||'var(--text-muted)';
    var isSel=r.ticker===etfSelTicker?' sr':'';
    var spyC=isSpy?' spy-row':'';
    var bw=r.chg_1d!=null?Math.min(Math.abs(r.chg_1d)/mx*32,32):0;
    var bc=r.chg_1d!=null&&r.chg_1d>=0?'var(--green-dim)':'var(--red-dim)';
    var mb=r.chg_1d!=null?'<div class="mb" style="width:'+bw+'px;background:'+bc+'"></div>':'';
    return '<tr class="'+isSel+spyC+'" onclick="selEtf(\''+r.ticker+'\','+i+')">'
      +'<td class="rk">'+(isSpy?'&#9733;':(i+1))+'</td>'
      +'<td class="tk" onmouseenter="showHtip(\''+r.ticker+'\',event)" onmouseleave="hideHtip()">'+r.ticker+'</td>'
      +'<td><span style="font-size:9px;color:'+sc+';letter-spacing:.06em">'+r.sector+'</span></td>'
      +'<td class="nm" title="'+r.name+'">'+r.name+'</td>'
      +'<td class="pr">'+p+'</td>'
      +'<td class="rs2">'+rsp+'</td>'
      +'<td class="tc '+hmCls(r.chg_1d)+'"><div class="ci">'+mb+fmtPct(r.chg_1d)+'</div></td>'
      +'<td class="tc '+hmCls(r.chg_1w)+'">'+fmtPct(r.chg_1w)+'</td>'
      +'<td class="tc '+hmCls(r.chg_1m)+'">'+fmtPct(r.chg_1m)+'</td>'
      +'<td class="tc '+hmCls(r.chg_3m)+'">'+fmtPct(r.chg_3m)+'</td>'
      +'<td class="tc '+hmCls(r.chg_ytd)+'">'+fmtPct(r.chg_ytd)+'</td>'
      +'</tr>';
  }
  if(spyRow&&mainRows!==rows)h+=makeEtfRow(spyRow,-1,true);
  mainRows.forEach(function(r,i){h+=makeEtfRow(r,i,false);});
  wrap.innerHTML=h+'</tbody></table>';
}

function selEtf(ticker,idx){
  etfSelTicker=ticker; etfSelIdx=idx; renderEtfTable();
  var rows=etfSort2(etfRows.filter(function(r){return etfSectorFilter==='ALL'||r.sector===etfSectorFilter;}));
  var sym=document.getElementById('etf-sym');if(!sym)return;
  sym.textContent=ticker;
  document.getElementById('etf-ctr').textContent=(idx+1)+' / '+rows.length;
  document.getElementById('etf-prev').disabled=idx<=0;
  document.getElementById('etf-next').disabled=idx>=rows.length-1;
  document.getElementById('etf-tv').href='https://www.tradingview.com/chart/?symbol='+ticker;
  document.getElementById('etf-fv').href='https://finviz.com/quote.ashx?t='+ticker;
  var empty=document.getElementById('etf-empty'),ifr=document.getElementById('etf-ifr');
  if(empty)empty.style.display='none'; ifr.style.display='block';
  var st='EMA%40tv-basicstudies%7CEMA%40tv-basicstudies%7CMASimple%40tv-basicstudies%7CMASimple%40tv-basicstudies';
  ifr.src='https://www.tradingview.com/widgetembed/?frameElementId=tv_e'
    +'&symbol='+encodeURIComponent(ticker)+'&interval=D&theme=dark&style=1'
    +'&toolbarbg=000000&withdateranges=1&locale=en&hidesidetoolbar=0'
    +'&studies='+st;
}
function slideEtf(dir){
  var rows=etfSort2(etfRows.filter(function(r){return etfSectorFilter==='ALL'||r.sector===etfSectorFilter;}));
  var ni=etfSelIdx+dir;if(ni<0||ni>=rows.length)return;selEtf(rows[ni].ticker,ni);
}

// HOVER
var htTimer=null;
function showHtip(t,e){
  clearTimeout(htTimer);
  htTimer=setTimeout(function(){
    document.getElementById('hts').textContent=t;
    document.getElementById('hti').src='https://finviz.com/chart.ashx?t='+t+'&ty=c&ta=0&p=d&s=l';
    posHtip(e); document.getElementById('htip').classList.add('vis');
  },280);
}
function hideHtip(){clearTimeout(htTimer);document.getElementById('htip').classList.remove('vis');}
function posHtip(e){var W=292,H=168,P=14,x=e.clientX+P,y=e.clientY+P;if(x+W>window.innerWidth)x=e.clientX-W-P;if(y+H>window.innerHeight)y=e.clientY-H-P;document.getElementById('htip').style.left=x+'px';document.getElementById('htip').style.top=y+'px';}
document.addEventListener('mousemove',function(e){if(document.getElementById('htip').classList.contains('vis'))posHtip(e);});

// CLEANUP
async function runCleanup(){
  var btn=document.getElementById('btn-clean'),orig=btn.textContent;
  btn.textContent='checking...';btn.disabled=true;
  try{
    var d=await(await fetch('/api/cleanup',{method:'POST'})).json();
    if(d.error){alert('Error: '+d.error);return;}
    if(d.total_removed===0)btn.textContent='OK';
    else{
      var msg='Removed '+d.total_removed+' dead tickers:\n\n';
      Object.entries(d.removed_map).forEach(function(e){msg+=e[0]+': '+e[1].join(', ')+'\n';});
      alert(msg);
      fetch('/api/themes').then(function(r){return r.json();}).then(function(r2){themeOrder=r2.order;themeCounts=r2.themes;perfData={};renderSidebar();if(activeTheme)loadTheme(activeTheme);else{renderPerfChart();loadPerfAll();}});
    }
    setTimeout(function(){btn.textContent=orig;btn.disabled=false;},2500);
  }catch(e){alert(e.message);btn.textContent=orig;btn.disabled=false;}
}

// MODALS
function om(id){document.getElementById(id).classList.add('open');}
function cm(id){document.getElementById(id).classList.remove('open');}
document.querySelectorAll('.mo').forEach(function(el){el.addEventListener('click',function(e){if(e.target===el)cm(el.id);});});
document.addEventListener('keydown',function(e){
  var modal=document.querySelector('.mo.open');
  if(modal){if(e.key==='Escape')cm(modal.id);return;}
  if(isEtf()){if(e.key==='ArrowDown'){e.preventDefault();slideEtf(1);}if(e.key==='ArrowUp'){e.preventDefault();slideEtf(-1);}}
  else if(activeTheme){if(e.key==='ArrowDown'){e.preventDefault();slideRow(1);}if(e.key==='ArrowUp'){e.preventDefault();slideRow(-1);}}
});
document.getElementById('add-inp').addEventListener('keydown',function(e){if(e.key==='Enter')doAdd();});
document.getElementById('peers-inp').addEventListener('keydown',function(e){if(e.key==='Enter')doFetchPeers();});
document.getElementById('new-inp').addEventListener('keydown',function(e){if(e.key==='Enter')doNew();});

boot();
</script>
</body>
</html>"""

if __name__ == "__main__":
    load_watchlists(); _load_file_cache()
    app.run(debug=False, port=5051)

# Vercel WSGI entry point — errors caught so cold start never crashes
try:
    load_watchlists()
    _load_file_cache()
except Exception as _startup_err:
    print(f"[startup] {_startup_err}")
