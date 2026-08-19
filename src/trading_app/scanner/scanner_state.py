from __future__ import annotations

from typing import Dict, Iterable, Optional
from trading_app.config import AppConfig


import logging

from trading_app.models.scanner_symbol import ScannerSymbolState
#
#  Quote Cache
#  Rolling Price History
#  Rolling Volume History
#
class ScannerState:
    """
    Owns all scanner-related runtime state.

    Responsibilities:
        * Current quote cache
        * ScannerSymbolState instances
        * Current scanner candidate symbols

    Does NOT perform momentum calculations.
    """

    def __init__(self, config: AppConfig ):

        self.config = config

        # Latest websocket quote by symbol
        self.quote_cache: Dict[str, dict] = {}

        # Rolling state for every tracked symbol
        self.symbols: Dict[str, ScannerSymbolState] = {}

        # Symbols currently matching scanner criteria
        self.candidates: set[str] = set()

        # Permanent scanner watch universe
        self.watch_symbols: set[str] = set()

        self.logger = logging.getLogger(__name__)


    # ------------------------------------------------------------------
    # Symbol management
    # ------------------------------------------------------------------

    def add_watch_symbol(self, symbol: str):
        symbol = symbol.upper()
        self.watch_symbols.add(symbol)
        #
        # Create ScannerSymbolState immediately so the
        # first websocket quote isn't dropped.
        #
        self.ensure_symbol(symbol)


    def remove_watch_symbol(self, symbol: str):
        symbol = symbol.upper()
        self.watch_symbols.discard(symbol)
        self.remove_symbol(symbol)

    def set_watch_symbols(self, symbols):
        desired = {s.upper() for s in symbols}
        #
        # Remove symbols no longer wanted
        #
        for symbol in self.watch_symbols - desired:
            self.remove_watch_symbol(symbol)
        #
        # Add new ones
        #
        for symbol in desired - self.watch_symbols:
            self.add_watch_symbol(symbol)


    def is_watch_symbol(self, symbol: str):
        return symbol.upper() in self.watch_symbols

        
    def ensure_symbol(self, symbol: str) -> ScannerSymbolState:
        symbol = symbol.upper()

        state = self.symbols.get(symbol)

        if state is None:
            state = ScannerSymbolState(symbol=symbol,
                    history_update_frequency_ms=self.config.history_update_frequency)
            self.symbols[symbol] = state

        return state

    def has_symbol(self, symbol: str) -> bool:

        return symbol.upper() in self.symbols

    def remove_symbol(self, symbol: str):

        symbol = symbol.upper()

        self.symbols.pop(symbol, None)
        self.quote_cache.pop(symbol, None)
        self.candidates.discard(symbol)

    def clear(self):

        self.symbols.clear()
        self.quote_cache.clear()
        self.candidates.clear()

    # ------------------------------------------------------------------
    # Quote updates
    # ------------------------------------------------------------------

    def update_quote(self, quote: dict):

        symbol = quote["symbol"].upper()

        # quote_cache is a fast lookup of the 
        # raw Schwab quote payload exactly as received.
        self.quote_cache[symbol] = quote

        #  ScannerSymbolState contains
        #  normalized fields plus rolling history and derived metrics.  
        state = self.ensure_symbol(symbol)

        state.update_quote(quote)

        return state

    def get_quote(self, symbol: str) -> Optional[dict]:

        return self.quote_cache.get(symbol.upper())

    # ------------------------------------------------------------------
    # Candidate management
    # ------------------------------------------------------------------

    def add_candidate(self, symbol: str):

        self.candidates.add(symbol.upper())

    def remove_candidate(self, symbol: str):

        self.candidates.discard(symbol.upper())
        self.symbols.pop(symbol, None)

    def is_candidate(self, symbol: str) -> bool:

        return symbol.upper() in self.candidates

    def clear_candidates(self):

        self.candidates.clear()

    def candidate_states(self) -> Iterable[ScannerSymbolState]:

        for symbol in self.candidates:
            state = self.symbols.get(symbol)

            if state is not None:
                yield state

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_display_snapshot(self):

        snapshot = {}

        for symbol, state in self.symbols.items():

            snapshot[symbol] = {
                "last": state.last,
                "bid": state.bid,
                "ask": state.ask,
                "volume": state.total_volume,

                #
                # default GUI period initially 60 seconds
                #
                "volume_pct": (
                    state.volume_change_from(60)
                    / state.total_volume * 100
                    if state.total_volume
                    else 0.0
                ),

                "price_pct": state.pct_1m,

                #
                # useful later
                #
                "dirty": getattr(
                    state,
                    "dirty",
                    False
                ),
            }

        return snapshot

    def dirty_snapshot(self):
        self.logger.debug("dirty_snapshot() called")
        snapshot = {}

        for symbol, state in self.symbols.items():

            if not state.dirty:
                continue

            snapshot[symbol] = {
                "last": state.last,
                "bid": state.bid,
                "ask": state.ask,
                "volume": state.total_volume,
                "volume_pct": state.volume_change_from(60),
                "price_pct": state.pct_1m,
                "momentum_score": state.momentum_score,
            }

            state.dirty = False

        return snapshot

    def get(self, symbol: str) -> Optional[ScannerSymbolState]:

        return self.symbols.get(symbol.upper())

    def values(self) -> Iterable[ScannerSymbolState]:

        return self.symbols.values()

    def items(self):

        return self.symbols.items()

    def __contains__(self, symbol: str):

        return symbol.upper() in self.symbols

    def __len__(self):

        return len(self.symbols)
    