"""
services/symbol_provider.py

Interface used by trading services to obtain the
currently selected trading symbol.

This isolates business logic from the GUI.
"""

from __future__ import annotations

from typing import Protocol


class SymbolProvider(Protocol):
    """
    Any object that can provide the currently
    selected trading symbol.

    Application already satisfies this protocol
    because it implements:

        get_selected_symbol() -> str
    """

    def get_selected_symbol(self) -> str:
        ...