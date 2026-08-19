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

import logging
import tkinter as tk
from tkinter import ttk, messagebox


from trading_app.gui.application_menus import (
    ApplicationMenus,
)

from trading_app.gui.table_renderer import (
    QuoteTable,
)

from trading_app.gui.status_bar import (
    StatusBar,
)

from trading_app.gui.trade_instruction_panel import (
    TradeInstructionPanel,
)

from trading_app.gui.momentum_table import (
    MomentumTable,
)

from trading_app.gui.theme import (configure_dark_theme, DARK)

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
    _SHIFT_SYMBOLS = {
        "!": "1",
        "@": "2",
        "#": "3",
        "$": "4",
        "%": "5",
        "^": "6",
        "&": "7",
        "*": "8",
        "(": "9",
        ")": "0",
    }

    def __init__(
        self,
        *,
        trading_config=None,
        trade_instruction_factory=None,
        hotkey_manager=None,
        get_quote=None,
        on_order=None,
        on_instruction_submit=None,
        on_connect=None,
        on_disconnect=None,
        on_reload_symbols=None,
        on_exit=None,
        on_add_symbol=None,
        on_remove_symbol=None,
        resolve_instruction=None,
        on_refresh_positions=None,
        on_account_changed=None,
        on_ensure_symbol=None,
        on_flatten_position=None,
        on_simulation_changed=None,
        on_get_quote=None,
    ):
        self.on_order = on_order
        self.trading_config = trading_config
        self.hotkey_manager = hotkey_manager
        self.trade_instruction_factory = (
            trade_instruction_factory
        )
        self.get_quote = get_quote
        self.on_instruction_submit = (on_instruction_submit)
        self.on_connect = (on_connect)
        self.on_disconnect = (on_disconnect)
        self.on_reload_symbols = on_reload_symbols
        self.on_exit = on_exit
        self.on_add_symbol = on_add_symbol
        self.on_remove_symbol = on_remove_symbol
        self.resolve_instruction = resolve_instruction
        self.on_refresh_positions = on_refresh_positions
        self.on_account_changed = on_account_changed
        self.on_ensure_symbol = on_ensure_symbol
        self.on_flatten_position = on_flatten_position
        self.on_simulation_changed = on_simulation_changed
        self.on_get_quote = on_get_quote

        self.root = tk.Tk()

        self.root.title(
            "Schwab Trading Terminal"
        )

        self.root.geometry(
            "1400x800"
        )

        self.style = configure_dark_theme(self.root)

        self.logger = logging.getLogger(__name__)

        self._build_layout()

        self._build_menu()
        self.root.protocol("WM_DELETE_WINDOW", self._exit)


    # -------------------------------------------------------------
    # Construction
    # -------------------------------------------------------------

    def _configure_dark_theme(self):
        style = ttk.Style(self.root)

        # Use a theme that permits customization.
        style.theme_use("clam")

        colors = DARK

        self.root.configure(bg=colors["bg"])

        style.configure(
            ".",
            background=colors["bg"],
            foreground=colors["fg"],
        )

        style.configure(
            "TFrame",
            background=colors["bg"],
        )

        style.configure(
            "TLabel",
            background=colors["bg"],
            foreground=colors["fg"],
        )

        style.configure(
            "TButton",
            background=colors["surface2"],
            foreground=colors["fg"],
            bordercolor=colors["border"],
        )

        style.map(
            "TButton",
            background=[
                ("active", colors["select_bg"]),
                ("pressed", colors["select_bg"]),
            ],
            foreground=[
                ("active", colors["select_fg"]),
            ],
        )

        style.configure(
            "TEntry",
            fieldbackground=colors["entry_bg"],
            foreground=colors["fg"],
            insertcolor=colors["fg"],
        )

        style.configure(
            "TCombobox",
            fieldbackground=colors["entry_bg"],
            background=colors["surface2"],
            foreground=colors["fg"],
            arrowcolor=colors["fg"],
        )

        style.map(
            "TCombobox",
            fieldbackground=[
                ("readonly", colors["entry_bg"]),
            ],
            foreground=[
                ("readonly", colors["fg"]),
            ],
        )

        style.configure(
            "TCheckbutton",
            background=colors["bg"],
            foreground=colors["fg"],
        )

        style.configure(
            "TLabelFrame",
            background=colors["bg"],
            foreground=colors["fg"],
        )

        style.configure(
            "TLabelFrame.Label",
            background=colors["bg"],
            foreground=colors["fg"],
        )

    def _on_key_press(self, event):

        #
        # Ignore auto-repeat
        #

        if event.keysym in ("Shift_L", "Shift_R",
                            "Control_L", "Control_R",
                            "Alt_L", "Alt_R"):
            return

        if self.hotkey_manager is None:
            return

        self.hotkey_manager.handle_key_event(event)

    def attach_hotkey_manager(self, manager):
        self.hotkey_manager = manager
        self.root.bind_all("<KeyPress>", self._on_key_press)

    def debug_key(self, event):
        print(
            f"keysym={event.keysym!r} "
            f"keycode={event.keycode} "
            f"char={event.char!r} "
            f"state=0x{event.state:04x}"
        )


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

#       self.root.bind_all("<KeyPress>", self.debug_key)

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

        

        left = ttk.Frame(main)

        left.grid(
            row=0,
            column=0,
            sticky="nsew",
        )


        left.rowconfigure(
            0,
            weight=3,
        )

        left.rowconfigure(
            1,
            weight=1,
        )


        left.columnconfigure(
            0,
            weight=1,
        )

        self.quote_table = QuoteTable(
                    left,
                    on_select=
                        self._symbol_selected,
                    on_delete=
                        self._remove_symbol,
                )

        self.quote_table.widget().grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.momentum_table = MomentumTable(
            left
        )


        self.momentum_table.widget().grid(
            row=1,
            column=0,
            sticky="nsew",
            pady=5,
        )

        #
        # Order panel
        #

        self.trade_instruction_panel = TradeInstructionPanel(
            main,
            on_submit=
                self._trade_instruction_submit,

            on_symbol_entered=
                self._add_symbol,

            on_account_changed=
                self._account_changed,

            resolve_instruction=
                self.resolve_instruction,

            on_get_quote=
                self.on_get_quote,

            trading_config=
                self.trading_config,

            trade_instruction_factory=
                self.trade_instruction_factory,
        )

        self.attach_hotkey_manager(self.hotkey_manager)

        self.trade_instruction_panel.widget().grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=5,
        )

        self.trade_instruction_panel.load_templates()


        #
        # Status bar
        #

        self.status_bar = StatusBar(
            self.root, on_simulation_changed=self._simulation_changed
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
            
            on_flatten_position=self._flatten_position,

            on_exit=
                self._exit,

            on_about=
                self._about,

            on_refresh=
                self._refresh_positions,

            on_reload_symbols=
                self._reload_symbols,
        )


    # -------------------------------------------------------------
    # GUI callbacks
    # -------------------------------------------------------------

    def _update_execution_indicator(self, enabled):
        if enabled:
            self.logger.debug("***** SIMULATION MODE ENABLED *****\n"
                "Orders will NOT be transmitted to Schwab.")

            self.status_bar.set_execution_mode(enabled)
            self.logger.debug(f"SIMULATION ENABLED: {enabled}")
        else:
            self.logger.debug(f"***** LIVE TRADING ENABLED {enabled}*****")
            if not messagebox.askyesno(
                "Enable Live Trading",
                "Simulation Mode will be disabled.\n\n"
                "REAL orders will be sent to Schwab.\n\n"
                "Continue?"
            ):
                self.logger.debug(f"***** LIVE TRADING REJECTED ? {enabled}*****")
                self.status_bar.set_execution_mode(tk.BooleanVar(value=True))
                return

            self.logger.debug("***** LIVE TRADING ENABLED2 *****")
            self.status_bar.set_execution_mode(enabled)
            

    def _simulation_changed(self, enabled):

        self.logger.debug(f"_simulation_changed: {enabled}")
        if self.on_simulation_changed:
            self.on_simulation_changed(enabled)

        self._update_execution_indicator(enabled)
            
        

    def set_accounts(
        self,
        accounts,
        default_account_number,
    ):
        self.logger.debug("APPLICATION set_accounts: %s", accounts)
        self.trade_instruction_panel.set_accounts(accounts, default_account_number)

    def _symbol_selected(
        self,
        symbol,
    ):

        self.logger.debug("APPLICATION: selected symbol: %s", symbol,)

        #
        # Change panel context first
        #

        self.trade_instruction_panel.set_symbol(
            symbol
        )


        #
        # Load most recent cached quote
        #

        if self.on_get_quote:

            quote = self.on_get_quote(
                symbol
            )
            self.logger.debug("APPLICATION cached quote: %s : %s", quote, type(quote),)

            if quote is not None:

                self.trade_instruction_panel.set_quote(
                    quote
                )

            else:

                #
                # No cached quote exists.
                # Clear stale values from previous symbol.
                #

                self.trade_instruction_panel.clear_quote()
                
    def get_selected_symbol(self):
        return (
            self.trade_instruction_panel
            .get_symbol()
        )

    def _trade_instruction_submit(
        self,
        instruction,
    ):
        """
        Receive TradeInstruction from GUI.

        The GUI does not know about:
            - Runtime
            - Broker
            - OrderRequest
        """

        if self.on_instruction_submit:

            self.on_instruction_submit(
                instruction
            )

    def _add_symbol(self, symbol):
        """Add a symbol typed in the trade panel to the watchlist and table."""

        symbol = symbol.strip().upper()

        if not symbol or symbol == "-":
            return

        if self.quote_table.find_symbol(symbol):
            self.quote_table.select_symbol(symbol)
            return

        if self.on_add_symbol and not self.on_add_symbol(symbol):
            return

        if self.quote_table.add_symbol(symbol):
            self.quote_table.select_symbol(symbol)

    def _remove_symbol(self, symbol):
        """Remove a table symbol and its market-data subscription."""

        if self.on_remove_symbol and not self.on_remove_symbol(symbol):
            return

        self.quote_table.remove_symbol(symbol)

        if self.trade_instruction_panel.selected_symbol == symbol.upper():
            self.trade_instruction_panel.set_symbol(None)
    
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

    def _reload_symbols(self):
        if self.on_reload_symbols:
            self.on_reload_symbols()

    def _exit(self):
        if self.on_exit:
            self.on_exit()
        else:
            self.shutdown()


    def _flatten_position(self):

        symbol = self.quote_table.get_selected_symbol()

        if not symbol:
            return

        self.on_flatten_position(symbol)

    def _about(self):

        messagebox.showinfo(
            "About",
            "Schwab Trading Terminal",
        )

    def _refresh_positions(self):
        if self.on_refresh_positions:
            self.on_refresh_positions()

    def _account_changed(
        self,
        account_hash: str | None,
    ):
        """
        Notify the runtime that the selected account changed.

        The runtime owns the authoritative selected-account state
        and is responsible for refreshing the displayed positions.
        """

        if (
            self.on_account_changed
            and account_hash is not None
        ):
            self.on_account_changed(
                account_hash
            )

    # -------------------------------------------------------------
    # Public API used by runtime
    # -------------------------------------------------------------

    def update_scanner(
        self,
        scanner_data,
    ):
        """
        Update momentum scanner display.

        Called from runtime after SCANNER_UPDATED 
        event.
        """
        self.logger.debug(
                "GUI received %d scanner symbols",
                len(scanner_data),
            )
        
        self.momentum_table.update_scanner(
            scanner_data
        )


    def update_quote(
        self,
        symbol,
        quote,
    ):
        self.logger.debug("GUI: %s", symbol)
        self.quote_table.update_quote(
            symbol,
            quote,
        )
        #
        # Only update trade panel
        # if it is watching this symbol.
        #
        if (
            self.trade_instruction_panel.selected_symbol
            == symbol
        ):
            self.trade_instruction_panel.set_quote(
                quote
            )

    def update_positions(self, quantities):

        if not quantities:
            return
        
        for symbol, quantity in quantities.items():
            self.on_ensure_symbol(symbol)
            self.quote_table.update_position(
                symbol,
                quantity,
            )

    def replace_symbols(self, symbols, positions=None):
        """Rebuild QuoteTable from current complete quotes after reload."""

        positions = (
            dict(self.quote_table.position_cache)
            if positions is None
            else dict(positions)
        )
        existing_quotes = dict(self.quote_table.row_cache)
        self.quote_table.clear()
        self.quote_table.position_cache.update(positions)

        # Position symbols must remain visible/actionable even when they were
        # not in either ticker file.  Prefer StateEngine's latest quote cache;
        # the pre-reload row cache covers the short event-queue race before a
        # fresh streaming update is delivered.
        refreshed_symbols = list(dict.fromkeys([*symbols, *positions]))
        for symbol in refreshed_symbols:
            quote = self.get_quote(symbol) if self.get_quote else None
            quote = quote or existing_quotes.get(symbol)
            if self._has_complete_quote(quote):
                self.quote_table.update_quote(symbol, quote)

        self.trade_instruction_panel.set_symbol(None)

    @staticmethod
    def _has_complete_quote(quote):
        if quote is None:
            return False

        for field in ("last", "bid", "ask", "volume"):
            value = quote.get(field) if isinstance(quote, dict) else getattr(quote, field, None)
            if value is None or value == "":
                return False
        return True

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
