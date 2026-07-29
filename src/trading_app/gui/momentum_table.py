"""
gui/momentum_table.py

Momentum scanner display.

Displays scanner-managed symbols and calculated metrics.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import logging

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


        self.rows = {}


    def widget(self):
        return self.frame


    def update_scanner(self, symbols):

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

            if symbol in self.rows:

                self.tree.item(
                    self.rows[symbol],
                    values=values,
                )

            else:

                iid = self.tree.insert(
                    "",
                    "end",
                    values=values,
                )

                self.rows[symbol] = iid

        #
        # Keep scanner ranked.
        #

        self.schedule_resort()