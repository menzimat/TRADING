"""
trading_config.py

Loads trading.yaml.

Convenience methods allow for:
cfg.templates["buy_limit"]

cfg.hotkeys["ctrl+b"]

cfg.price_offsets["default"]

cfg.defaults["tif"]

"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

@dataclass(frozen=True)
class TradingConfig:

    data: dict

    @classmethod
    def load(cls, filename):

        path = Path(filename)

        if not path.exists():
            raise FileNotFoundError(path)

        with path.open() as f:
            data = yaml.safe_load(f)

        return cls(data=data)
    
    @property
    def defaults(self):
        return self.data["defaults"]

    @property
    def hotkeys(self):
        return self.data["hotkeys"]

    @property
    def templates(self):
        return self.data["templates"]

    @property
    def price_offsets(self):
        return self.data["price_offsets"]