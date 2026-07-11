"""
models/broker_account.py

Broker account model.

Represents a brokerage account available to the
authenticated user.

This model is independent of any particular broker
implementation and is suitable for GUI display.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BrokerAccount:
    """
    Broker account metadata.

    display_name
        Human-readable text shown in the GUI.

    account_number
        Broker account number.

    account_hash
        Broker-specific identifier required by
        the Schwab streaming and trading APIs.
    """

    display_name: str

    account_number: str

    account_hash: str

    def __str__(self) -> str:
        return self.display_name