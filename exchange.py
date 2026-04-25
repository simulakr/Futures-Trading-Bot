import ccxt
import logging
import pandas as pd
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from config import BINANCE_API_KEY, BINANCE_API_SECRET, TESTNET

logger = logging.getLogger(__name__)

BINANCE_MAX_LIMIT = 1000  # Binance Futures fetch_ohlcv limiti


class BinanceFuturesClient:
    """ccxt üzerinden Binance USDM Futures bağlantısı."""

    def __init__(self):
        options = {
            "defaultType":            "future",
            "adjustForTimeDifference": True,
        }
        if TESTNET:
            options["urls"] = {
                "api": {
                    "public":  "https://testnet.binancefuture.com",
                    "private": "https://testnet.binancefuture.com",
                }
            }

        self.client = ccxt.binance({
            "apiKey":  BINANCE_API_KEY,
            "secret":  BINANCE_API_SECRET,
            "options": options,
        })

        # Cache: {symbol: DataFrame (1000 bar, index=UTC datetime)}
        self._cache: Dict[str, pd.DataFrame] = {}

        self._load_markets()
        logger.info("Binance Futures bağlantısı kuruldu (Testnet: %s)", TESTNET)

    # ─── Market Bilgisi ───────────────────────────────────────────────────────

    def _load_markets(self) -> None:
        try:
            self.markets = self.client.load_markets()
        except Exception as exc:
            logger.error("Market bilgileri yüklenemedi: %s", exc)
            self.markets = {}

    def get_server_time_ms(self) -> int:
        return self.client.fetch_time()

    # ─── Tekli OHLCV ──────────────────────────────────────────────────────────

    def get_ohlcv(
        self,
        symbol:           str,
        interval:         str = "15m",
        limit:            int = BINANCE_MAX_LIMIT,
        convert_to_float: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        Tek sembol için OHLCV verisi çeker.
        Index: UTC datetime, sütunlar: open high low close volume
        """
        try:
            raw = self.client.fetch_ohlcv(symbol, timeframe=interval, limit=limit)
            df  = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume"])
            df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
            df.set_index("time", inplace=True)
            if convert_to_float:
                df = df.astype(float)
            return df
        except Exception as exc:
            logger.error("OHLCV çekme hatası (%s): %s", symbol, exc)
            return None

    # ─── Cache Başlatma ───────────────────────────────────────────────────────

    def initialize_cache(self, symbols: List[str], interval: str = "15m") -> None:
        """
        Bot başlarken her sembol için 1000 bar çekip cache'e yükler.
        Paralel çalışır.
        """
        logger.info("Cache başlatılıyor: %s", symbols)
        with ThreadPoolExecutor(max_workers=len(symbols)) as executor:
            futures = {
                sym: executor.submit(self.get_ohlcv, sym, interval, BINANCE_MAX_LIMIT)
                for sym in symbols
            }
            for sym, fut in futures.items():
                df = fut.result()
                if df is not None and not df.empty:
                    self._cache[sym] = df
                    logger.info("%s cache hazır (%d bar)", sym, len(df))
                else:
                    logger.error("%s cache başlatılamadı", sym)

    # ─── Cache Güncelleme ─────────────────────────────────────────────────────

    def update_cache(self, symbol: str, interval: str = "15m", fetch_last: int = 3) -> Optional[pd.DataFrame]:
        """
        Her mumda sadece son 3 bar çeker, cache'e ekler, 1000 bar sınırını korur.
        Güncel DataFrame döndürür.
        """
        try:
            new_bars = self.get_ohlcv(symbol, interval, limit=fetch_last)
            if new_bars is None or new_bars.empty:
                logger.warning("%s yeni bar çekilemedi, cache kullanılıyor", symbol)
                return self._cache.get(symbol)

            if symbol not in self._cache:
                logger.warning("%s cache yok, 1000 bar çekiliyor", symbol)
                df = self.get_ohlcv(symbol, interval, BINANCE_MAX_LIMIT)
                if df is not None:
                    self._cache[symbol] = df
                return self._cache.get(symbol)

            # Yeni barları cache'e ekle
            combined = pd.concat([self._cache[symbol], new_bars])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined.sort_index(inplace=True)

            # 1000 bar sınırını koru
            combined = combined.iloc[-1000:]
            self._cache[symbol] = combined
            return combined

        except Exception as exc:
            logger.error("%s cache güncelleme hatası: %s", symbol, exc)
            return self._cache.get(symbol)

    # ─── Ana Veri Çekme (Cache'li) ────────────────────────────────────────────

    def get_multiple_ohlcv(
        self,
        symbols:  List[str],
        interval: str = "15m",
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Her mumda tüm semboller için cache günceller, güncel DataFrame döndürür.
        Cache yoksa otomatik başlatır.
        """
        missing = [s for s in symbols if s not in self._cache]
        if missing:
            self.initialize_cache(missing, interval)

        with ThreadPoolExecutor(max_workers=len(symbols)) as executor:
            futures = {
                sym: executor.submit(self.update_cache, sym, interval)
                for sym in symbols
            }
            return {sym: fut.result() for sym, fut in futures.items()}

    # ─── Hesap & Kaldıraç ─────────────────────────────────────────────────────

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        try:
            self.client.set_leverage(leverage, symbol)
            logger.info("%s kaldıraç ayarlandı: %sx", symbol, leverage)
            return True
        except ccxt.ExchangeError as exc:
            if "No need to change leverage" in str(exc):
                logger.debug("%s kaldıraç zaten %sx", symbol, leverage)
                return True
            logger.warning("%s kaldıraç ayarlama hatası: %s", symbol, exc)
            return False

    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED") -> bool:
        try:
            self.client.set_margin_mode(margin_type.lower(), symbol)
            logger.info("%s margin tipi: %s", symbol, margin_type)
            return True
        except ccxt.ExchangeError as exc:
            if "No need to change margin type" in str(exc):
                return True
            logger.warning("%s margin tipi ayarlama hatası: %s", symbol, exc)
            return False

    def get_open_positions(self) -> List[Dict]:
        try:
            positions = self.client.fetch_positions()
            return [p for p in positions if abs(float(p.get("contracts", 0) or 0)) > 0]
        except Exception as exc:
            logger.error("Pozisyonlar alınamadı: %s", exc)
            return []

    def get_position(self, symbol: str) -> Optional[Dict]:
        try:
            positions = self.client.fetch_positions([symbol])
            for pos in positions:
                if abs(float(pos.get("contracts", 0) or 0)) > 0:
                    return pos
            return None
        except Exception as exc:
            logger.error("%s pozisyon alınamadı: %s", symbol, exc)
            return None

    # ─── Emir İşlemleri ───────────────────────────────────────────────────────

    def place_market_order(
        self,
        symbol:      str,
        side:        str,
        amount:      float,
        reduce_only: bool = False,
    ) -> Optional[Dict]:
        try:
            params = {"reduceOnly": reduce_only}
            order  = self.client.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=amount,
                params=params,
            )
            logger.info("Market emir gönderildi: %s %s %s adet", symbol, side.upper(), amount)
            return order
        except Exception as exc:
            logger.error("Market emir hatası (%s %s): %s", symbol, side, exc)
            return None

    def place_limit_order(
        self,
        symbol:        str,
        side:          str,
        amount:        float,
        price:         float,
        reduce_only:   bool = False,
        time_in_force: str  = "GTC",
    ) -> Optional[Dict]:
        try:
            params = {
                "reduceOnly":  reduce_only,
                "timeInForce": time_in_force,
            }
            order = self.client.create_order(
                symbol=symbol,
                type="limit",
                side=side,
                amount=amount,
                price=price,
                params=params,
            )
            logger.info("Limit emir gönderildi: %s %s %.5f @ %.5f", symbol, side.upper(), amount, price)
            return order
        except Exception as exc:
            logger.error("Limit emir hatası (%s %s): %s", symbol, side, exc)
            return None

    def place_stop_market_order(
        self,
        symbol:      str,
        side:        str,
        amount:      float,
        stop_price:  float,
        reduce_only: bool = True,
    ) -> Optional[Dict]:
        try:
            params = {
                "stopPrice":  stop_price,
                "reduceOnly": reduce_only,
            }
            order = self.client.create_order(
                symbol=symbol,
                type="stop_market",
                side=side,
                amount=amount,
                params=params,
            )
            logger.info("Stop-Market emir gönderildi: %s %s stop=%.5f", symbol, side.upper(), stop_price)
            return order
        except Exception as exc:
            logger.error("Stop-Market emir hatası (%s %s): %s", symbol, side, exc)
            return None

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        try:
            try:
                self.client.cancel_order(order_id, symbol)
                logger.info("Emir iptal edildi: %s / %s", symbol, order_id)
                return True
            except Exception:
                pass

            raw_symbol = symbol.replace("/", "").replace(":USDT", "")
            self.client.fapiPrivateDeleteAlgoOrder({
                "symbol": raw_symbol,
                "algoId": order_id,
            })
            logger.info("Algo emir iptal edildi: %s / %s", symbol, order_id)
            return True

        except ccxt.OrderNotFound:
            logger.debug("Emir zaten yok: %s / %s", symbol, order_id)
            return True
        except Exception as exc:
            logger.error("Emir iptal hatası (%s / %s): %s", symbol, order_id, exc)
            return False

    def get_order(self, symbol: str, order_id: str) -> Optional[Dict]:
        try:
            return self.client.fetch_order(order_id, symbol)
        except ccxt.OrderNotFound:
            return None
        except Exception as exc:
            logger.error("Emir sorgulama hatası (%s / %s): %s", symbol, order_id, exc)
            return None

    def get_open_orders(self, symbol: str) -> List[Dict]:
        try:
            return self.client.fetch_open_orders(symbol)
        except Exception as exc:
            logger.error("Açık emirler alınamadı (%s): %s", symbol, exc)
            return []
