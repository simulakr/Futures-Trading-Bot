import os
from dotenv import load_dotenv

load_dotenv()

# ─── Binance API ──────────────────────────────────────────────────────────────
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
TESTNET            = os.getenv("TESTNET", "false").lower() == "true"

# ─── Semboller & Zaman Aralığı ────────────────────────────────────────────────
SYMBOLS  = [ 'BTCUSDC',"ETHUSDC", "SOLUSDT", "XRPUSDT", "DOGEUSDT"] #"BTCUSDT","BNBUSDT"
INTERVAL = "15m"

# ─── Percent ATR Filtreleri ───────────────────────────────────────────────────
ATR_RANGES = {'SOLUSDT':  (0.401, 1.176), 
              'BTCUSDT': (0.179, 0.648), 
               'ETHUSDT':  (0.317, 0.990), 
              'DOGEUSDT':  (0.421, 1.306), 
              'XRPUSDT':  (0.340, 1.378),  
              }

# ─── Z Göstergesi: atr.quantile(0.25 - 0.55) ────────────────────────────────────────────────────────────
Z_RANGES = {
    'BTCUSDC': (0.181, 0.272),
    'ETHUSDC': (0.325, 0.466),
    'SOLUSDT': (0.399, 0.555),
    'DOGEUSDT': (0.432, 0.621),
    'XRPUSDT': (0.341, 0.525),
}

Z_INDICATOR_PARAMS = {
    "atr_period":     14,
    "atr_multiplier": 1,
}

# ─── Pozisyon Büyüklüğü ───────────────────────────────────────────────────────
QUANTITY_PRECISION = {
    "BTCUSDC":  3,
    "ETHUSDC":  2,
    "SOLUSDT":  1,
    "XRPUSDT":  0,
    "DOGEUSDT": 0,
}

PRICE_PRECISION = {
    "BTCUSDC":  2,
    "ETHUSDC":  2,
    "SOLUSDT":  3,
    "XRPUSDT":  4,
    "DOGEUSDT": 5,
}


# ─── Risk & Kaldıraç ─────────────────────────────────────────────────────────

DEFAULT_LEVERAGE  = 25
DEFAULT_RISK_USDT = 10

SYMBOL_SETTINGS = {
    "BTCUSDC":  {"risk": 10, "leverage": 25},
    "ETHUSDC":  {"risk": 10, "leverage": 25},
    "SOLUSDT":  {"risk": 10, "leverage": 25},
    "XRPUSDT":  {"risk": 10, "leverage": 25},
    "DOGEUSDT": {"risk": 10, "leverage": 25},
}

# ─── TP / SL Çarpanları ───────────────────────────────────────────────────────
TP_ATR_MULTIPLIER = 2.25
SL_ATR_MULTIPLIER = 2.25
