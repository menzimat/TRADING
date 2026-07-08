"""
gui/application.py

Main GUI composition root.

Responsibilities:
    - Create Tk application
    - Compose GUI components
    - Connect callbacks

Non-responsibilities:
    - Trading logic
    - Broker communication
    - Market data handling
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox


from trading_app.gui.application_menus import (
    ApplicationMenus,
)

from trading_app.gui.table_renderer import (
    QuoteTable,
)

from trading_app.gui.order_panel import (
    OrderPanel,
)

from trading_app.gui.status_bar import (
    StatusBar,
)


class TradingApplication:
    """
    Main trading GUI.

    The runtime layer creates this object.

    Example:

        gui = TradingApplication(
            on_order=processor.submit,
        )

        gui.run()

    """

    def __init__(
        self,
        *,
        on_order=None,
        on_connect=None,
        on_disconnect=None,
    ):

        self.on_order = on_order

        self.on_connect = (
            on_connect
        )

        self.on_disconnect = (
            on_disconnect
        )


        self.root = tk.Tk()

        self.root.title(
            "Schwab Trading Terminal"
        )

        self.root.geometry(
            "1400x800"
        )


        self._build_layout()

        self._build_menu()


    # -------------------------------------------------------------
    # Construction
    # -------------------------------------------------------------

    def _build_layout(self):

        self.root.columnconfigure(
            0,
            weight=1,
        )

        self.root.rowconfigure(
            0,
            weight=1,
        )


        main = ttk.Frame(
            self.root
        )

        main.grid(
            row=0,
            column=0,
            sticky="nsew",
        )


        main.columnconfigure(
            0,
            weight=3,
        )

        main.columnconfigure(
            1,
            weight=1,
        )


        main.rowconfigure(
            0,
            weight=1,
        )


        #
        # Quote table
        #

        self.quote_table = QuoteTable(
            main,
            on_select=
                self._symbol_selected,
        )

        self.quote_table.widget().grid(
            row=0,
            column=0,
            sticky="nsew",
        )


        #
        # Order panel
        #

        self.order_panel = OrderPanel(
            main,
            on_order=self._order_request,
        )

        self.order_panel.widget().grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=5,
        )


        #
        # Status bar
        #

        self.status_bar = StatusBar(
            self.root
        )

        self.status_bar.widget().grid(
            row=1,
            column=0,
            sticky="ew",
        )


    def _build_menu(self):

        self.menus = ApplicationMenus(
            self.root,

            on_connect=
                self._connect,

            on_disconnect=
                self._disconnect,

            on_exit=
                self.shutdown,

            on_about=
                self._about,
        )


    # -------------------------------------------------------------
    # GUI callbacks
    # -------------------------------------------------------------

    def _symbol_selected(
        self,
        symbol,
    ):

        self.order_panel.set_symbol(
            symbol
        )


    def _order_request(
        self,
        request,
    ):

        if self.on_order:

            self.on_order(
                request
            )


    def _connect(self):

        if self.on_connect:

            self.on_connect()


    def _disconnect(self):

        if self.on_disconnect:

            self.on_disconnect()


    def _about(self):

        messagebox.showinfo(
            "About",
            "Schwab Trading Terminal",
        )


    # -------------------------------------------------------------
    # Public API used by runtime
    # -------------------------------------------------------------

    def update_quote(
        self,
        symbol,
        quote,
    ):
        print("GUI:", symbol)
        self.quote_table.update_quote(
            symbol,
            quote,
        )


    def set_connection_status(
        self,
        status,
    ):

        self.status_bar.set_connection(
            status
        )


    def set_market_status(
        self,
        status,
    ):

        self.status_bar.set_market_state(
            status
        )


    def run(self):

        self.root.mainloop()


    def shutdown(self):

        self.root.destroy()