"""
config.py

Application configuration.

Configuration is loaded once during startup.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULTS = {

    "app_ip": "127.0.0.1",
    "app_port": 55665,
    "socket_path": "/tmp/schwab.sock",
    "token_path": "./tokens/token.json",
    "tickers_file": "./cfg/tickers.txt",
    "trading_config": "./cfg/trading.yaml",
    "keepass_config": "./cfg/config.json",
    "history_update_frequency": 500,
    "momentum": {
        "enabled": True,
        "use_schwab_movers": True,
        "movers_poll_interval": 6,
        "movers_frequency": 5,
        "movers_direction": "up",
        "max_movers": 10,
        "merge_scanner_file": True,"min_mover_price": 5.0,
        "max_mover_price": 20.0,
        "min_volume": 5000000
    },
    "logging": {
        "root_level": "INFO",
        "modules": {},
        "console": True,
        "file": True,
        "filename": "logs/trading.log",
        "rotation": {
            "max_mb": 10,
            "backups": 5,
        },
    },
    "quote_refresh_ms": 20,
    "market_queue_size": 1000,
    "command_queue_size": 200,
    "review_orders": True,
    "default_buy_offset": 0.10,
    "default_sell_offset": 0.10,
    "default_stop_offset": 0.40,


}

@dataclass(frozen=True)
class MomentumSettings:
    use_schwab_movers: bool = True
    movers_poll_interval: int = 6
    movers_frequency: int = 5
    movers_direction: str = "up"
    max_movers: int = 10
    merge_scanner_file: bool = True
    delete_scanner_symbols = False
    min_mover_price: float = 0.7
    max_mover_price: float = 20.0
    min_volume: int = 5000000


@dataclass(frozen=True)
class AppConfig:

    app_ip: str

    app_port: int

    socket_path: str

    token_path: str

    tickers_file: str

    trading_config: str

    keepass_config: str

    history_update_frequency: int

    logging: dict[str, Any]

    quote_refresh_ms: int

    market_queue_size: int

    command_queue_size: int

    review_orders: bool

    default_buy_offset: float

    default_sell_offset: float

    default_stop_offset: float

    momentum: MomentumSettings = field(default_factory=MomentumSettings)

    @classmethod
    def load(

        cls,

        filename="./cfg/app.json"

    ):

        cfg = DEFAULTS.copy()

        path = Path(filename)

        if path.exists():

            cfg.update(

                json.loads(

                    path.read_text()

                )

            )

        return cls(**cfg)
        
    def get_trading_config_path(self):
        return Path(self.trading_config).resolve()

    def get_keepass_config_path(self):
        return Path( self.keepass_config ).resolve()
    