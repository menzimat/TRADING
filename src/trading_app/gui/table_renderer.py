"""
gui/table_renderer.py

QuoteTable - Tkinter Treeview based quote display.

Responsibilities:
    - Render quote rows
    - Incrementally update rows
    - Maintain row cache
    - Provide symbol lookup
    - Sorting
    - Visual price/percent coloring
    - Selection callbacks

Non-responsibilities:
    - Networking
    - Market data subscriptions
    - Order handling
    - Application coordination
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional, Any


class QuoteTable:
    """
    Quote table widget.

    Public interface:
        update_quote(symbol, quote)
        remove_symbol(symbol)
        clear()
        get_selected_symbol()
        get_quote(symbol)

    Callbacks:
        on_select(symbol)
    """

    COLUMNS = (
        "symbol",
        "last",
        "bid",
        "ask",
        "volume",
        "position",
    )

    HEADINGS = {
        "symbol": "Symbol",
        "last": "Last",
        "bid": "Bid",
        "ask": "Ask",
        "volume": "Volume",
        "position": "Position",
    }

    COLUMN_WIDTHS = {
        "symbol": 80,
        "last": 80,
        "bid": 80,
        "ask": 80,
        "volume": 100,
        "position": 90,
    }

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_select: Optional[Callable[[str], None]] = None,
        on_delete: Optional[Callable[[str], None]] = None,
    ):
        self.parent = parent

        self.on_select = on_select
        self.on_delete = on_delete

        #
        # Internal row cache:
        #
        # {
        #     "AAPL": {
        #          "last": 190.25,
        #          ...
        #     }
        # }
        #
        self.row_cache: Dict[str, Any] = {}
        self.position_cache: Dict[str, int] = {}

        #
        # Tree item lookup:
        #
        # symbol -> tree iid
        #
        self.symbol_rows: Dict[str, str] = {}
        self.suppressed_symbols = set()

        self.sort_column: Optional[str] = None
        self.sort_reverse = False

        self.frame = ttk.Frame(parent)

        self.tree = ttk.Treeview(
            self.frame,
            columns=self.COLUMNS,
            show="headings",
            selectmode="browse",
        )

        self.context_menu = tk.Menu(self.tree, tearoff=False)
        self.context_menu.add_command(
            label="Delete",
            command=self._delete_context_symbol,
        )
        self._context_symbol = None

        self._build_columns()
        self._configure_styles()
        self._bind_events()

        self.tree.pack(
            fill="both",
            expand=True,
        )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_columns(self):
        for column in self.COLUMNS:
            self.tree.heading(
                column,
                text=self.HEADINGS[column],
                command=lambda c=column: self.sort_by(c),
            )

            self.tree.column(
                column,
                width=self.COLUMN_WIDTHS[column],
                anchor="center",
            )

    def _configure_styles(self):

        self.tree.tag_configure(
            "positive",
            foreground="green",
        )

        self.tree.tag_configure(
            "negative",
            foreground="red",
        )

        self.tree.tag_configure(
            "neutral",
            foreground="black",
        )

    def _bind_events(self):

        self.tree.bind(
            "<<TreeviewSelect>>",
            self._selection_changed,
        )
        self.tree.bind("<Button-3>", self._show_context_menu)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def widget(self):
        """
        Return Tk widget container.
        """
        return self.frame


    def update_quote(
        self,
        symbol: str,
        quote: Any,
    ):
        """
        Incrementally update one quote.

        quote may be:
            dict
            dataclass
            object with attributes
        """

        symbol = symbol.upper()

        if symbol in self.suppressed_symbols:
            return

        old_quote = self.row_cache.get(symbol)

        self.row_cache[symbol] = quote

        values = self._quote_to_row(symbol, quote)

        if symbol in self.symbol_rows:

            iid = self.symbol_rows[symbol]

            self.tree.item(
                iid,
                values=values,
                tags=(
                    self._price_tag(
                        old_quote,
                        quote
                    ),
                ),
            )

        else:

            iid = self.tree.insert(
                "",
                "end",
                values=values,
                tags=(
                    self._price_tag(
                        None,
                        quote
                    ),
                ),
            )

            self.symbol_rows[symbol] = iid

    def add_symbol(
        self,
        symbol: str,
    ) -> bool:
        """Add an empty quote row for a newly watched symbol.

        Quote updates later replace this placeholder through ``update_quote``.
        """

        symbol = symbol.strip().upper()

        if not symbol or symbol in self.symbol_rows:
            return False

        self.suppressed_symbols.discard(symbol)
        self.row_cache[symbol] = {"symbol": symbol}
        iid = self.tree.insert(
            "",
            "end",
            values=(symbol, "", "", "", "", self._position_value(symbol)),
            tags=("neutral",),
        )
        self.symbol_rows[symbol] = iid
        return True


    def select_symbol(
        self,
        symbol: str,
    ) -> bool:
        """Focus and select a displayed symbol."""

        iid = self.find_symbol(symbol)

        if not iid:
            return False

        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self.tree.see(iid)
        return True


    def remove_symbol(
        self,
        symbol: str,
    ):

        symbol = symbol.upper()
        self.suppressed_symbols.add(symbol)

        iid = self.symbol_rows.pop(
            symbol,
            None,
        )

        if iid:

            self.tree.delete(iid)

        self.row_cache.pop(
            symbol,
            None,
        )

    def update_position(self, symbol: str, quantity: int):
        """Update a displayed symbol's aggregate Schwab position."""

        symbol = symbol.upper()
        self.position_cache[symbol] = int(quantity)
        iid = self.symbol_rows.get(symbol)
        if not iid:
            return

        quote = self.row_cache.get(symbol, {"symbol": symbol})
        self.tree.item(iid, values=self._quote_to_row(symbol, quote))

    def set_positions(self, quantities):
        """Replace displayed positions when the selected account changes."""

        self.position_cache = {
            symbol.upper(): int(quantity)
            for symbol, quantity in quantities.items()
        }
        for symbol, iid in self.symbol_rows.items():
            quote = self.row_cache.get(symbol, {"symbol": symbol})
            self.tree.item(iid, values=self._quote_to_row(symbol, quote))


    def clear(self):

        for iid in self.tree.get_children():

            self.tree.delete(iid)

        self.row_cache.clear()
        self.position_cache.clear()
        self.symbol_rows.clear()
        self.suppressed_symbols.clear()


    def get_quote(
        self,
        symbol: str,
    ):

        return self.row_cache.get(
            symbol.upper()
        )


    def get_selected_symbol(
        self,
    ) -> Optional[str]:

        selected = self.tree.selection()

        if not selected:
            return None

        values = self.tree.item(
            selected[0],
            "values",
        )

        return values[0]


    def find_symbol(
        self,
        symbol: str,
    ) -> Optional[str]:

        return self.symbol_rows.get(
            symbol.upper()
        )


    # ------------------------------------------------------------------
    # Selection handling
    # ------------------------------------------------------------------

    def _selection_changed(
        self,
        event=None,
    ):

        symbol = self.get_selected_symbol()

        if symbol and self.on_select:

            self.on_select(symbol)

    def _show_context_menu(self, event):
        """Show Delete only for a right-click on a symbol cell."""

        iid = self.tree.identify_row(event.y)

        if (
            not iid
            or self.tree.identify_region(event.x, event.y) != "cell"
            or self.tree.identify_column(event.x) != "#1"
        ):
            return

        values = self.tree.item(iid, "values")
        if not values:
            return

        self._context_symbol = values[0]
        self.tree.selection_set(iid)
        self.tree.focus(iid)

        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

        return "break"

    def _delete_context_symbol(self):
        if self._context_symbol and self.on_delete:
            self.on_delete(self._context_symbol)

        self._context_symbol = None


    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def sort_by(
        self,
        column: str,
    ):

        if self.sort_column == column:

            self.sort_reverse = not self.sort_reverse

        else:

            self.sort_column = column
            self.sort_reverse = False


        rows = []

        for iid in self.tree.get_children():

            value = self.tree.set(
                iid,
                column,
            )

            rows.append(
                (
                    self._sortable_value(value),
                    iid,
                )
            )


        rows.sort(
            reverse=self.sort_reverse
        )


        for index, (_, iid) in enumerate(rows):

            self.tree.move(
                iid,
                "",
                index,
            )


    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _quote_to_row(
        self,
        symbol,
        quote,
    ):

        return (
            symbol,
            self._field(quote, "last"),
            self._field(quote, "bid"),
            self._field(quote, "ask"),
            self._field(quote, "volume"),
            self._position_value(symbol),
        )

    def _position_value(self, symbol):
        return self.position_cache.get(symbol.upper(), 0)


    @staticmethod
    def _field(
        obj,
        name,
    ):

        if isinstance(obj, dict):

            return obj.get(name, "")

        return getattr(
            obj,
            name,
            "",
        )


    def _price_tag(
        self,
        old,
        new,
    ):

        if old is None:
            return "neutral"

        old_price = self._field(
            old,
            "last",
        )

        new_price = self._field(
            new,
            "last",
        )


        try:

            if new_price > old_price:
                return "positive"

            if new_price < old_price:
                return "negative"

        except TypeError:
            pass


        return "neutral"


    @staticmethod
    def _sortable_value(
        value,
    ):

        try:
            return float(
                str(value)
                .replace("%", "")
                .replace(",", "")
            )

        except ValueError:

            return str(value).lower()
