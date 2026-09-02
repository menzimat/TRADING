"""
gui/momentum_table.py

Momentum scanner display.

Displays scanner-managed symbols and calculated metrics.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import logging
from trading_app.gui.theme import DARK

class MomentumTable:

    COLUMNS = (
        "symbol",
        "last",
        "bid",
        "ask",
        "volume",
        "volume_pct",
        "price_pct",
        "momentum_score",
    )

    SORT_OPTIONS = (
        "Momentum",
        "Price %",
        "Average Volume",
        "Total Volume",
        "Last",
        "Symbol",
    )

    def sort_by(self, column):

        reverse = False

        if getattr(self, "_sort_column", None) == column:
            reverse = not getattr(self, "_sort_reverse", False)

        self._sort_column = column
        self._sort_reverse = reverse

        rows = []

        for iid in self.tree.get_children(""):

            value = self.tree.set(iid, column)

            #
            # Convert numeric columns
            #
            if column != "symbol":
                try:
                    value = float(
                        value.replace("%", "").replace(",", "")
                    )
                except ValueError:
                    value = 0.0

            rows.append((value, iid))

        rows.sort(
            key=lambda row: row[0],
            reverse=reverse,
        )

        for index, (_, iid) in enumerate(rows):
            self.tree.move(iid, "", index)


    def get_column_width(self, column):
        width = 90
        if column == "symbol":
            width = 80
        elif column == "last":
            width = 75
        elif column == "bid":
            width = 75
        elif column == "ask":
            width = 75
        elif column == "volume":
            width = 110
        elif column == "volume_pct":
            width = 85
        elif column == "price_pct":
            width = 85
        elif column == "momentum_score":
            width = 90

        return width

    def refresh_all_rows(self):
        """
        Refresh all displayed rows using the currently selected
        momentum period.

        This is the sole Treeview rendering path.
        """

        period = self.period_seconds.get()

        period_map = {
            5: {
                "price_pct": "pct_5s",
                "volume_rate": "avg_vol_30s",
            },
            10: {
                "price_pct": "pct_10s",
                "volume_rate": "avg_vol_30s",
            },
            30: {
                "price_pct": "pct_30s",
                "volume_rate": "avg_vol_30s",
            },
            60: {
                "price_pct": "pct_1m",
                "volume_rate": "avg_vol_1m",
            },
            300: {
                "price_pct": "pct_5m",
                "volume_rate": "avg_vol_5m",
            },
        }

        metrics = period_map.get(period)

        if metrics is None:
            self.logger.warning(
                "Unsupported momentum period: %s",
                period,
            )
            return

        price_key = metrics["price_pct"]
        volume_key = metrics["volume_rate"]

        for symbol, data in self.row_data.items():

            iid = self.rows.get(symbol)

            if iid is None:
                continue

            values = (
                symbol,
                f"{data.get('last', 0):.2f}",
                f"{data.get('bid', 0):.2f}",
                f"{data.get('ask', 0):.2f}",
                f"{data.get('volume', 0):,}",
                f"{data.get(volume_key, 0):,.0f}",
                f"{data.get(price_key, 0):.2f}%",
                f"{data.get('momentum_score', 0):.2f}",
            )

            if symbol in self.new_symbols:
                tag = "new"
            else:
                old_data = self.previous_row_data.get(symbol)
                tag = self._price_tag(old_data, data)

            self.tree.item(
                iid,
                values=values,
                tags=(tag,),
            )


    def old_refresh_all_rows(self):
        """
        Refresh displayed rows using the currently selected momentum period.

        The scanner payload already contains all calculated metrics.
        This method only selects the appropriate period metrics and updates
        the GUI rows.
        """

        period = self.period_seconds.get()

        period_map = {
            5: {
                "price_pct": "pct_5s",
                "volume_rate": "avg_vol_30s",
            },
            10: {
                "price_pct": "pct_10s",
                "volume_rate": "avg_vol_30s",
            },
            30: {
                "price_pct": "pct_30s",
                "volume_rate": "avg_vol_30s",
            },
            60: {
                "price_pct": "pct_1m",
                "volume_rate": "avg_vol_1m",
            },
            300: {
                "price_pct": "pct_5m",
                "volume_rate": "avg_vol_5m",
            },
        }

        metrics = period_map.get(period)

        if metrics is None:
            self.logger.warning(
                "Unsupported momentum period: %s",
                period,
            )
            return


        price_key = metrics["price_pct"]
        volume_key = metrics["volume_rate"]


        for symbol, data in self.row_data.items():

            values = (
                symbol,
                f"{data.get('last', 0):.2f}",
                f"{data.get('bid', 0):.2f}",
                f"{data.get('ask', 0):.2f}",
                f"{data.get('volume', 0):,}",

                #
                # Average shares/sec, not percentage
                #
                f"{data.get(volume_key, 0):,.0f}",

                #
                # True price percentage change
                #
                f"{data.get(price_key, 0):.2f}%",

                f"{data.get('momentum_score', 0):.2f}",
            )


            iid = self.rows.get(symbol)

            if iid is not None:

                self.tree.item(
                    iid,
                    values=values,
                )

    def _period_changed(self, event=None):
        self.logger.info(
            "Momentum period changed to %d seconds",
            self.period_seconds.get(),
        )

        self.refresh_all_rows()
        self.resort()

    def resort(self):

            metric = self.sort_selection.get()

            if metric == "Symbol":

                ordered = sorted(
                    self.row_data.items()
                )

            else:

                field = self.sort_keys[metric]

                ordered = sorted(
                    self.row_data.items(),
                    key=lambda item: item[1].get(field, 0),
                    reverse=True,
                )

            for index, (symbol, _) in enumerate(ordered):

                iid = self.rows.get(symbol)

                if iid is not None:

                    self.tree.move(
                        iid,
                        "",
                        index,
                    )


    def old_resort(self):
        metric = self.sort_selection.get()

        if metric == "Symbol":

            ordered = sorted(
                self.row_data.items()
            )

        else:

            field = self.sort_keys[metric]

            ordered = sorted(
                self.row_data.items(),
                key=lambda item: item[1].get(field, 0),
                reverse=True,
            )

        for index, (symbol, _) in enumerate(ordered):
            self.tree.move(
                self.rows[symbol],
                "",
                index,
            )


    def _perform_resort(self):
        self.sort_after_id = None
        if self.sort_needed:
            self.sort_needed = False
            self.resort()


    def _sort_changed(self, event=None):
        self.logger.info("Sort changed to %s", self.sort_selection.get())
        if self.sort_after_id is not None:
            self.frame.after_cancel(self.sort_after_id)
            self.sort_after_id = None
        self.resort()




    def schedule_resort(self):
        """
        Schedule a resort if one is not already pending.
        """
        self.sort_needed = True

        if self.sort_after_id is not None:
            return

        self.sort_after_id = self.frame.after(
            self.sort_interval_ms,
            self._perform_resort,
        )

    def __init__(self, parent):


        self.logger = logging.getLogger(__name__)

        self.row_data = {}
        self.previous_row_data = {}
        self.new_symbols = set()

        self.sort_keys = {
            "Momentum": "momentum_score",
            "Price %": "price_pct",
            "Average Volume": "volume_pct",
            "Total Volume": "volume",
            "Last": "last",
        }

        self.sort_after_id = None

        #
        # milliseconds between automatic resorts
        #
        self.sort_interval_ms = 250

        self.sort_needed = False

        self.frame = ttk.LabelFrame(
            parent,
            text="Momentum Scanner"
        )

        #
        # Selected statistics period
        #

        self.period_seconds = tk.IntVar(
            value=60
        )

        self.sort_selection = tk.StringVar(
            value="Momentum"
        )

        controls = ttk.Frame(
            self.frame
        )

        controls.pack(
            fill="x",
            padx=5,
            pady=3
        )


        ttk.Label(
            controls,
            text="Period:"
        ).pack(
            side="left"
        )


        periods = (
            5,
            10,
            30,
            60,
            300,
        )


        self.period_box = ttk.Combobox(
            controls,
            textvariable=self.period_seconds,
            values=periods,
            width=8,
            state="readonly",
        )

        self.period_box.pack(
            side="left",
            padx=5,
        )

        self.period_box.bind(
            "<<ComboboxSelected>>",
            self._period_changed,
        )

        ttk.Label(
            controls,
            text="Sort:"
        ).pack(
            side="left",
            padx=(20, 5),
        )

        self.sort_box = ttk.Combobox(
            controls,
            textvariable=self.sort_selection,
            values=self.SORT_OPTIONS,
            width=14,
            state="readonly",
        )

        self.sort_box.pack(
            side="left",
        )

        self.sort_box.bind(
            "<<ComboboxSelected>>",
            self._sort_changed,
        )

        #
        # Table
        #

        self.tree = ttk.Treeview(
            self.frame,
            columns=self.COLUMNS,
            show="headings",
            height=8,
            style="Dark.Treeview",
        )

        self.tree.tag_configure(
            "neutral",
            foreground=DARK["neutral"],
        )

        self.tree.tag_configure(
            "positive",
            foreground=DARK["positive"],
        )

        self.tree.tag_configure(
            "negative",
            foreground=DARK["negative"],
        )

        # Persistent highlight for symbols newly added to the scanner.
        self.tree.tag_configure(
            "new",
            background=DARK.get("select_bg", "#555555"),
            foreground=DARK.get("select_fg", DARK["fg"]),
        )

        headings = {
            "symbol": "Symbol",
            "last": "Last",
            "bid": "Bid",
            "ask": "Ask",
            "volume": "Total Volume",
            "volume_pct": "Avg Vol/sec",
            "price_pct": "Price %",
            "momentum_score": "Momentum",
        }


        for column in self.COLUMNS:

            self.tree.heading(
                column,
                text=headings[column],
                command=lambda c=column: self.sort_by(c),
            )


            self.tree.column(
                column,
                width=self.get_column_width(column),
                anchor="center",
            )




        self.tree.pack(
            fill="both",
            expand=True,
        )

        # A click acknowledges a NEW row and removes its persistent highlight.
        self.tree.bind("<Button-1>", self._acknowledge_new_row)

        self.rows = {}


    def widget(self):
        return self.frame


    def _momentum_tag(self, data):
        """
        Return the Treeview color tag based on price momentum.
        """

        try:
            price_pct = float(data.get("price_pct", 0))

        except (TypeError, ValueError):
            return "neutral"

        if price_pct > 0:
            return "positive"

        if price_pct < 0:
            return "negative"

        return "neutral"

    def _price_tag(self, old, new):
        """
        Return the Treeview color tag based on change in ``last`` price.

        This mirrors QuoteTable: existing rows are green/positive when the
        latest last price is above the previous snapshot and red/negative
        when it is below. Rows without a usable previous price are neutral.
        """

        if old is None:
            return "neutral"

        def field(obj, name):
            if isinstance(obj, dict):
                return obj.get(name)
            return getattr(obj, name, None)

        try:
            old_price = float(field(old, "last"))
            new_price = float(field(new, "last"))
        except (TypeError, ValueError):
            return "neutral"

        if new_price > old_price:
            return "positive"

        if new_price < old_price:
            return "negative"

        return "neutral"

    def _acknowledge_new_row(self, event):
        """Remove the persistent NEW highlight when a row is clicked."""

        iid = self.tree.identify_row(event.y)
        if not iid:
            return

        values = self.tree.item(iid, "values")
        if not values:
            return

        symbol = values[0]
        if symbol not in self.new_symbols:
            return

        self.new_symbols.discard(symbol)

        data = self.row_data.get(symbol)
        if data is None:
            return

        old_data = self.previous_row_data.get(symbol)
        self.tree.item(
            iid,
            tags=(self._price_tag(old_data, data),),
        )


    def new_update_scanner(self, symbols):
        """
        Replace the current scanner snapshot and refresh the table.

        Rendering is handled exclusively by refresh_all_rows().
        """

        if symbols is None:
            return

        self.logger.debug(
            "Momentum scanner update type: %s",
            type(symbols),
        )

        self.logger.debug(
            "Momentum scanner received %d symbols",
            len(symbols),
        )

        #
        # Preserve the previous snapshot so price coloring can compare the
        # latest ``last`` value against the preceding scanner update.
        #
        self.previous_row_data = self.row_data.copy()
        self.row_data = dict(symbols)

        #
        # Remove rows for symbols no longer present.
        #
        current_symbols = set(symbols)

        for symbol, iid in list(self.rows.items()):

            if symbol not in current_symbols:

                self.tree.delete(iid)
                del self.rows[symbol]

        #
        # Create rows for newly discovered symbols.
        #
        for symbol in symbols:

            if symbol in self.rows:
                continue

            iid = self.tree.insert(
                "",
                "end",
                values=("",) * len(self.COLUMNS),
                tags=("neutral",),
            )

            self.rows[symbol] = iid
            self.new_symbols.add(symbol)

        # NEW state only applies to symbols still present in the snapshot.
        self.new_symbols.intersection_update(current_symbols)

        #
        # Single rendering path.
        #
        self.refresh_all_rows()

        #
        # Rank after rendering.
        #
        self.schedule_resort()

    def update_scanner(self, symbols):
        """
        Update the scanner data cache and refresh the table.

        Rendering is handled exclusively by refresh_all_rows().
        This method does not construct Treeview values directly.
        """

        if not symbols:
            return

        self.logger.debug(
            "Momentum scanner update type: %s",
            type(symbols),
        )

        self.logger.debug(
            "Momentum scanner received %d symbols",
            len(symbols),
        )

        #
        # Update the authoritative scanner data cache.
        #
        for symbol, data in symbols.items():
            if symbol in self.row_data:
                self.previous_row_data[symbol] = self.row_data[symbol]
            self.row_data[symbol] = data

        #
        # Create Treeview rows for any new symbols.
        #
        for symbol in symbols:

            if symbol in self.rows:
                continue

            iid = self.tree.insert(
                "",
                "end",
                values=("",) * len(self.COLUMNS),
                tags=("neutral",),
            )

            self.rows[symbol] = iid
            self.new_symbols.add(symbol)

        #
        # There is now exactly one rendering path.
        #
        self.refresh_all_rows()

        #
        # Keep scanner ranked.
        #
        self.schedule_resort()


    def old_update_scanner(self, symbols):

        if not symbols:
            return
        
        self.logger.debug(type(symbols))
        self.logger.debug(symbols)

        for symbol, data in symbols.items():
            self.row_data[symbol] = data
        
            values = (
                symbol,
                f"{data['last']:.2f}",
                f"{data['bid']:.2f}",
                f"{data['ask']:.2f}",
                data["volume"],
                f"{data['volume_pct']:.0f}",
                f"{data['price_pct']:.2f}%",
                f"{data['momentum_score']:.2f}",
            )
            tag = self._momentum_tag(data)
            if symbol in self.rows:
                self.tree.item(
                    self.rows[symbol],
                    values=values,
                    tags=(tag,),
                )
            else:
                iid = self.tree.insert(
                    "",
                    "end",
                    values=values,
                    tags=(tag,),
                )

                self.rows[symbol] = iid

        #
        # Keep scanner ranked.
        #
        self.schedule_resort()