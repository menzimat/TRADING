"""
gui/order_panel.py

OrderPanel

Responsibilities:
    - Collect order parameters from user
    - Display selected symbol
    - Generate OrderRequest objects
    - Notify application through callback

Non-responsibilities:
    - Broker communication
    - Order validation beyond UI checks
    - Risk management
    - Position management
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

from trading_app.models.order import OrderRequest


class OrderPanel:
    """
    Trading order entry panel.

    Public interface:

        set_symbol(symbol)

    Callback:

        on_order(OrderRequest)
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_order: Optional[
            Callable[[OrderRequest], None]
        ] = None,
    ):

        self.parent = parent
        self.on_order = on_order

        self.current_symbol: Optional[str] = None

        self.frame = ttk.LabelFrame(
            parent,
            text="Order Entry",
        )

        self._build_ui()


    # -------------------------------------------------------------
    # Construction
    # -------------------------------------------------------------

    def _build_ui(self):

        self.symbol_var = tk.StringVar(
            value="-"
        )

        self.qty_var = tk.StringVar(
            value="100"
        )

        self.price_var = tk.StringVar(
            value=""
        )


        self.order_type_var = tk.StringVar(
            value="MARKET"
        )


        #
        # Symbol
        #

        ttk.Label(
            self.frame,
            text="Symbol",
        ).grid(
            row=0,
            column=0,
            padx=5,
            pady=5,
        )


        ttk.Label(
            self.frame,
            textvariable=self.symbol_var,
            width=10,
        ).grid(
            row=0,
            column=1,
        )


        #
        # Quantity
        #

        ttk.Label(
            self.frame,
            text="Quantity",
        ).grid(
            row=1,
            column=0,
        )


        ttk.Entry(
            self.frame,
            textvariable=self.qty_var,
            width=10,
        ).grid(
            row=1,
            column=1,
        )


        #
        # Order Type
        #

        ttk.Label(
            self.frame,
            text="Type",
        ).grid(
            row=2,
            column=0,
        )


        ttk.Combobox(
            self.frame,
            textvariable=self.order_type_var,
            values=[
                "MARKET",
                "LIMIT",
            ],
            state="readonly",
            width=10,
        ).grid(
            row=2,
            column=1,
        )


        #
        # Limit Price
        #

        ttk.Label(
            self.frame,
            text="Limit",
        ).grid(
            row=3,
            column=0,
        )


        ttk.Entry(
            self.frame,
            textvariable=self.price_var,
            width=10,
        ).grid(
            row=3,
            column=1,
        )


        #
        # Buttons
        #

        ttk.Button(
            self.frame,
            text="BUY",
            command=lambda:
                self._submit("BUY"),
        ).grid(
            row=4,
            column=0,
            padx=5,
            pady=10,
        )


        ttk.Button(
            self.frame,
            text="SELL",
            command=lambda:
                self._submit("SELL"),
        ).grid(
            row=4,
            column=1,
            padx=5,
            pady=10,
        )


        ttk.Button(
            self.frame,
            text="CANCEL",
            command=self._cancel,
        ).grid(
            row=5,
            column=0,
            columnspan=2,
            pady=5,
        )


    # -------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------

    def widget(self):

        return self.frame


    def set_symbol(
        self,
        symbol: Optional[str],
    ):

        self.current_symbol = (
            symbol.upper()
            if symbol
            else None
        )

        self.symbol_var.set(
            self.current_symbol
            or "-"
        )


    # -------------------------------------------------------------
    # Order creation
    # -------------------------------------------------------------

    def _submit(
        self,
        side: str,
    ):

        if not self.current_symbol:

            messagebox.showwarning(
                "Missing Symbol",
                "Select a symbol first.",
            )

            return


        try:

            quantity = int(
                self.qty_var.get()
            )

            if quantity <= 0:
                raise ValueError


        except ValueError:

            messagebox.showerror(
                "Invalid Quantity",
                "Quantity must be positive.",
            )

            return


        price = None

        if (
            self.order_type_var.get()
            == "LIMIT"
        ):

            try:

                price = float(
                    self.price_var.get()
                )

            except ValueError:

                messagebox.showerror(
                    "Invalid Price",
                    "Limit order requires price.",
                )

                return



        request = OrderRequest(
            symbol=self.current_symbol,
            side=side,
            quantity=quantity,
            order_type=
                self.order_type_var.get(),
            price=price,
        )


        if self.on_order:

            self.on_order(request)



    def _cancel(self):

        self.price_var.set("")

        self.order_type_var.set(
            "MARKET"
        )