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
from typing import Optional
from pathlib import Path
import yaml
from trading_app.models.order import (
    Side,
    OrderType,
    TimeInForce,
)

from enum import Enum
from copy import deepcopy

# ---------------------------------------------------------
# Trading configuration enums
# ---------------------------------------------------------

class QuantityType(str, Enum):

    FIXED = "fixed"

    RISK = "risk"

    DOLLARS = "dollars"

    PERCENT = "percent"


class PriceBasis(str, Enum):

    BID = "bid"

    ASK = "ask"

    LAST = "last"

    MARKET = "market"


class OffsetUnits(str, Enum):

    DOLLARS = "dollars"

    PERCENT = "percent"

    TICKS = "ticks"


@dataclass(slots=True)
class ResolvedPriceOffset:
    value: float
    units: str          # dollars | percent | ticks

# ---------------------------------------------------------
# Quantity
# ---------------------------------------------------------

@dataclass(frozen=True)
class QuantityDefinition:

    type: QuantityType          # fixed | risk | percent

    value: int


# ---------------------------------------------------------
# Price
# ---------------------------------------------------------

@dataclass(frozen=True)
class PriceDefinition:

    basis: PriceBasis         # ask | bid | market

    offset: Optional[str] = None


# ---------------------------------------------------------
# Named offsets
# ---------------------------------------------------------

@dataclass(frozen=True)
class OffsetDefinition:

    value: float

    units: OffsetUnits         # dollars | ticks | percent


# ---------------------------------------------------------
# Trading defaults
# ---------------------------------------------------------

@dataclass(frozen=True)
class TradingDefaults:

    side: Side

    account: str

    quantity: QuantityDefinition

    tif: TimeInForce

    order_type: OrderType

    price_basis: PriceBasis

    price_offset: str


# ---------------------------------------------------------
# Templates
# ---------------------------------------------------------

@dataclass(frozen=True)
class TemplateDefinition:

    #
    # Action templates
    #

    action: Optional[str] = None

    #
    # Order templates
    #

    side: Optional[Side] = None

    order_type: Optional[OrderType] = None

    quantity: Optional[QuantityDefinition] = None

    price: Optional[PriceDefinition] = None

    tif: Optional[TimeInForce] = None

@dataclass(frozen=True)
class TradingConfig:

    defaults: TradingDefaults
    price_offsets: dict[str, OffsetDefinition]
    hotkeys: dict[str, str]
    templates: dict[str, TemplateDefinition]

    def get_hotkey(self, key: str) -> dict | None:
        return self.config["hotkeys"].get(key)

    def get_template(self, name: str) -> dict | None:
        return self.config["templates"].get(name)


    def merge_dict(self, base: dict, overrides: dict) -> dict:

        result = deepcopy(base)

        for key, value in overrides.items():

            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self.merge_dict(result[key], value)

            else:
                result[key] = deepcopy(value)

        return result

    @classmethod
    def load(
        cls,
        filename,
    ):

        path = Path(filename)

        if not path.exists():
            raise FileNotFoundError(path)

        with path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        #
        # ---------------------------------------------------------
        # Defaults
        # ---------------------------------------------------------
        #

        defaults_cfg = cfg["defaults"]

        defaults = TradingDefaults(
            side=Side[defaults_cfg["side"].upper()],
            account=defaults_cfg["account"],
            quantity=QuantityDefinition(
                type=QuantityType(
                    defaults_cfg["quantity"]["type"].lower()
                ),
                value=int(
                    defaults_cfg["quantity"]["value"]
                ),
            ),
            tif=TimeInForce[
                defaults_cfg["tif"].upper()
            ],
            order_type=OrderType[
                defaults_cfg["order_type"].upper()
            ],
            price_basis=PriceBasis(
                defaults_cfg["price_basis"].lower()
            ),
            price_offset=defaults_cfg["price_offset"],
        )

        #
        # ---------------------------------------------------------
        # Named price offsets
        # ---------------------------------------------------------
        #

        offsets = {}

        for name, value in cfg["price_offsets"].items():

            offsets[name] = OffsetDefinition(

                value=float(
                    value["value"]
                ),

                units=OffsetUnits(
                    value["units"].lower()
                ),
            )

        #
        # ---------------------------------------------------------
        # Templates
        # ---------------------------------------------------------
        #

        templates = {}

        for name, value in cfg["templates"].items():

            #
            # Action templates
            #

            if "action" in value:

                templates[name] = TemplateDefinition(
                    action=value["action"],
                )

                continue

            templates[name] = TemplateDefinition(

                side=Side[
                    value["side"].upper()
                ],

                order_type=OrderType[
                    value["order_type"].upper()
                ],

                quantity=QuantityDefinition(

                    type=QuantityType(
                        value["quantity"]["type"].lower()
                    ),

                    value=int(
                        value["quantity"]["value"]
                    ),
                ),

                price=PriceDefinition(

                    basis=PriceBasis(
                        value["price"]["basis"].lower()
                    ),

                    offset=value["price"].get(
                        "offset"
                    ),
                ),

                tif=TimeInForce[
                    value["tif"].upper()
                ],
            )

        #
        # ---------------------------------------------------------
        # Hotkeys
        # ---------------------------------------------------------
        #

        hotkeys = dict(
            cfg.get("hotkeys", {})
        )

        #
        # ---------------------------------------------------------
        # Finished configuration
        # ---------------------------------------------------------
        #

        return TradingConfig(
            defaults=defaults,
            price_offsets=offsets,
            hotkeys=hotkeys,
            templates=templates,
        )
    
    def resolve_price_offset(self, offset):
        """
        Resolve a template price offset.

        Input may be:

            "default"
            "aggressive"
            "passive"
            "market"

        or

            0.02
            -0.05

        Returns:

            ResolvedPriceOffset(
                value=float,
                units=str
            )
        """

        #
        # Already numeric
        #

        if isinstance(offset, (int, float)):
            return ResolvedPriceOffset(
                value=float(offset),
                units="dollars",
            )

        #
        # Named offset
        #

        if not isinstance(offset, str):
            raise TypeError(
                f"Unsupported offset type: {type(offset)}"
            )

        try:
            cfg = self.price_offsets[offset]
        except KeyError:
            raise ValueError(
                f"Unknown price offset '{offset}'."
            )

        return ResolvedPriceOffset(
            value=float(cfg.value),
            units=cfg.units,
        )
    
    def resolve_quantity_value(
        self,
        quantity_type,
        value,
    ):
        """
        Resolve template quantity.

        Returns a numeric quantity.

        fixed:
            Shares

        percent:
            Percentage of current position

        risk:
            Dollar risk

        """

        #
        # Already numeric
        #

        if isinstance(value, (int, float)):
            return value

        #
        # Future symbolic quantities
        #

        if not isinstance(value, str):
            raise TypeError(
                f"Unsupported quantity value: {value}"
            )

        #
        # Example future aliases
        #

        aliases = {

            "default":
                self.defaults.quantity.value,

            "small":
                100,

            "medium":
                250,

            "large":
                500,

        }

        try:
            return aliases[value]

        except KeyError:

            raise ValueError(
                f"Unknown quantity alias '{value}'."
            )
    