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
    )

    def __init__(self, parent):


        self.logger = logging.getLogger(__name__)

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
            "volume_pct": "Volume %",
            "price_pct": "Price %",
        }


        for column in self.COLUMNS:

            self.tree.heading(
                column,
                text=headings[column],
            )

            self.tree.column(
                column,
                width=90,
                anchor="center",
            )


        self.tree.pack(
            fill="both",
            expand=True,
        )


        self.rows = {}


    def widget(self):
        return self.frame


    def old_update_scanner(
        self,
        symbols,
    ):
        """
        Receive scanner metrics.

        Expected:

        {
            "AAPL": {
                "last": 123,
                "bid": 122.9,
                "ask":123.1,
                "volume":100000,
                "volume_pct":12.5,
                "price_pct":1.2
            }
        }
        """
        if not symbols:
            return
    
        for symbol, data in symbols.items():

            values = (
                symbol,
                data.get("last"),
                data.get("bid"),
                data.get("ask"),
                data.get("volume"),
                data.get("volume_pct"),
                data.get("price_pct"),
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

    def update_scanner(self, symbols):

        if not symbols:
            return
        
        self.logger.info(type(symbols))
        self.logger.info(symbols)

        for symbol, data in symbols.items():

            values = (
                symbol,
                f"{data['last']:.2f}",
                f"{data['bid']:.2f}",
                f"{data['ask']:.2f}",
                data["volume"],
                f"{data['volume_pct']:.2f}%",
                f"{data['price_pct']:.2f}%",
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