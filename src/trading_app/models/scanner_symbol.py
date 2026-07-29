from dataclasses import dataclass, field
from collections import deque
from time import monotonic
import logging

@dataclass(slots=True, frozen=True)
class ScannerTick:
    timestamp: float
    price: float
    cumulative_volume: int

#
#  per-symbol statistics
#
@dataclass(slots=True)
class ScannerSymbolState:


    logger = logging.getLogger(__name__)

    symbol: str

    # current quote

    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0

    session_open: float = 0.0

    total_volume: int = 0

    previous_total_volume: int = 0

    last_update: float = 0.0

    # rolling tick history

    history: deque[ScannerTick] = field(default_factory=lambda: deque(maxlen=3600))
    history_update_frequency_ms: int = 250

    # derived statistics

    pct_open: float = 0.0

    pct_5s: float = 0.0
    pct_10s: float = 0.0
    pct_30s: float = 0.0

    pct_1m: float = 0.0
    pct_5m: float = 0.0
    pct_15m: float = 0.0

    avg_vol_30s: float = 0.0
    avg_vol_1m: float = 0.0
    avg_vol_5m: float = 0.0

    relative_volume: float = 0.0

    momentum_score: float = 0.0

    candidate = False

    dirty: bool = False
    
    def should_append_history(
        self,
        timestamp: float,
        history_update_frequency_ms: int | None = None,
    ) -> bool:
        """
        Decide whether this websocket update should become
        a history sample.

        Append when:
        - history is empty
        - price changed
        - cumulative volume changed
        - configured sample interval elapsed
        """

        if not self.history:
            return True

        if history_update_frequency_ms is None:
            history_update_frequency_ms = self.history_update_frequency_ms

        last_tick = self.history[-1]

        #
        # Market activity always wins.
        #
        if self.last != last_tick.price:
            return True

        if self.total_volume != last_tick.cumulative_volume:
            return True

        #
        # Otherwise maintain periodic samples.
        #
        elapsed_ms = (timestamp - last_tick.timestamp) * 1000.0

        return elapsed_ms >= history_update_frequency_ms

    def update_quote(self, quote: dict):
        #
        #  Responsibilities:
        #  update bid
        #  update ask
        #  update last
        #  update total volume
        #  append history
        #  purge expired history
        #  recalculate statistics
        #
        now = monotonic()

        #
        #
        #
        old_values = (
            self.bid,
            self.ask,
            self.last,
            self.total_volume,
        )

        #
        # Preserve previous cumulative volume
        #
        self.previous_total_volume = self.total_volume

        #
        # Update latest quote values
        #
        self.bid = quote.get("bid", quote.get("bidPrice", self.bid))
        self.ask = quote.get("ask", quote.get("askPrice", self.ask))

        self.last = (
            quote.get("last")
            or quote.get("lastPrice")
            or quote.get("mark")
            or self.last
        )

        self.session_open = quote.get(
            "openPrice",
            quote.get("open", self.session_open),
        )

        self.total_volume = quote.get(
            "totalVolume",
            quote.get("volume", self.total_volume),
        )

        self.last_update = now

        
        new_values = (
            self.bid,
            self.ask,
            self.last,
            self.total_volume,
        )

        if old_values != new_values:
            self.dirty = True
            self.logger.debug(
                "scanner_symmbol updating DIRTY for %s",
                self.symbol,
            )

        #
        # Maintain rolling history
        #
        if self.should_append_history(now):
            self.append_tick(now)
            self.purge_old_history()
            self.logger.debug(
                            "scanner_symmbol updated history at %s",
                            str(now),
                        )

        #
        # Refresh derived statistics
        #
        self.update_statistics()
        self.logger.debug(
                        "scanner_symmbol updated statistics")


     


    def append_tick(self, timestamp: float):
        self.history.append(
            ScannerTick(
                timestamp=timestamp,
                price=self.last,
                cumulative_volume=self.total_volume,))
        

    def purge_old_history(self, max_seconds: int = 900):
        now = monotonic()
        while self.history:
            if now - self.history[0].timestamp <= max_seconds:
                break
            self.history.popleft()

    def volume_change_from(self, seconds):

        old_volume = self.volume_at_age(seconds)

        if old_volume is None:
            return 0

        return max(0, self.total_volume - old_volume)

    
    #  eliminates duplicated math in update_statistics()
    def pct_change_from(self, reference):
        if not reference:
            return 0.0
        return ((self.last - reference) / reference) * 100.0


    #  rolling volume helper
    def volume_at_age(self, seconds):
        cutoff = monotonic() - seconds
        for tick in self.history:
            if tick.timestamp >= cutoff:
                return tick.cumulative_volume
        if self.history:
            return self.history[0].cumulative_volume
        return None


    def price_at_age(self, seconds):
        cutoff = monotonic() - seconds
        for tick in self.history:
            if tick.timestamp >= cutoff:
                return tick.price
        if self.history:
            return self.history[0].price
        return None


    def price_5_seconds_ago(self):
        return self.price_at_age(5)
    
    def price_30_seconds_ago(self):
        return  self.price_at_age(30)

    def price_5_minutes_ago(self):
        return self.price_at_age(300)

    def update_statistics(self):
        #
        #   updates
        #  pct_open
        #  pct_5s
        #  pct_10s
        #  pct_30s
        #  pct_1m
        #  pct_5m
        #  pct_15m
        #  average volumes
        #  relative volume
        #  from the stored history.  Every quote automatically refreshes every statistic.
        #
        self.pct_open = self.pct_change_from(self.session_open)

        self.pct_5s = self.pct_change_from(self.price_at_age(5))
        self.pct_10s = self.pct_change_from(self.price_at_age(10))
        self.pct_30s = self.pct_change_from(self.price_at_age(30))

        self.pct_1m = self.pct_change_from(self.price_at_age(60))
        self.pct_5m = self.pct_change_from(self.price_at_age(300))
        self.pct_15m = self.pct_change_from(self.price_at_age(900))

        self.avg_vol_30s = self.volume_change_from(30) / 30.0
        self.avg_vol_1m = self.volume_change_from(60) / 60.0
        self.avg_vol_5m = self.volume_change_from(300) / 300.0

        #
        # Placeholder until historical baseline exists.
        #
        self.relative_volume = 0.0

        #
        # Momentum scoring comes later.
        #
        self.momentum_score = 0.0