"""
gui/trade_instruction_panel.py

TradeInstructionPanel

Responsibilities:

    - Display current TradeInstruction
    - Allow user edits
    - Select YAML trading template
    - Show live quote information
    - Submit TradeInstruction

Non-responsibilities:

    - Broker communication
    - OrderRequest creation
    - Price calculation
    - Risk management
"""

from __future__ import annotations


import pprint
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional


from trading_app.models.trade_instruction import (
    TradeInstruction,
)

from trading_app.models.order import (
    Side,
    OrderType,
    TimeInForce,
)

from trading_app.trading_config import (
    QuantityType,
    PriceBasis,
    OffsetUnits,
)

from trading_app.services.price_calculator import (
                PriceCalculator,
            )

class TradeInstructionPanel:
    """
    Tkinter trade instruction editor.
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_submit: Optional[
            Callable[[TradeInstruction], None]
        ] = None,
        trading_config=None,
        trade_instruction_factory=None,
    ):
        self._loading_instruction = False
        self.on_submit = on_submit

        self.trading_config = (
            trading_config
        )

        self.trade_instruction_factory = (
            trade_instruction_factory
        )

        self.instruction: Optional[
            TradeInstruction
        ] = None

        self.current_quote = None
        self.selected_symbol = None
        self.accounts = None
        self.frame = ttk.LabelFrame(
            parent,
            text="Trade Instruction",
        )
        

        self._build_variables()
        
        self._build_ui()



    # =========================================================
    # Variables
    # =========================================================

    def load_instruction(
        self,
        instruction,
    ):
        self._loading_instruction = True
        try:
            self.instruction = instruction

            

            self.side_var.set(
                instruction.side.name
            )

            self.order_type_var.set(
                instruction.order_type.name
            )

            self.tif_var.set(
                instruction.tif.name
            )


            self.quantity_var.set(
                str(
                    instruction.quantity_value
                )
            )


            self.price_basis_var.set(
                instruction.price_basis.name
            )


            self.offset_value.set(
                str(
                    instruction.offset_value
                )
            )

            self.offset_units_var.set(
                instruction.offset_units.name
            )

            self.review_var.set(
                instruction.review_before_send
            )

            if instruction.manual_order_price is None:
                self.manual_price_var.set("")
            else:
                self.manual_price_var.set(
                    str(
                        instruction.manual_order_price
                    )
                )

            self._display_instruction()
            
        finally:
            self._loading_instruction = False
    
    def _recalculate(self):

        if not self.instruction:
            return


        PriceCalculator.apply(
            self.instruction
        )


        self.base_price_var.set(
            self._fmt(
                self.instruction.base_price
            )
        )


        self.order_price_var.set(
            self._fmt(
                self.instruction.order_price
            )
        )

    def _manual_price_changed(
        self,
        *_
    ):
        if not self.instruction:
            return

        value = self.manual_price_var.get().strip()

        if not value:
            self.instruction.manual_order_price = None
            self._recalculate()
            return

        try:
            self.instruction.manual_order_price = float(value)
        except ValueError:
            return

        self._recalculate()

    def _offset_changed(
        self,
        *_,
    ):
        if not self.instruction:
            return

        try:

            self.instruction.offset_value = float(
                self.offset_value.get()
            )

        except ValueError:

            return


        self._recalculate()

    def _offset_units_changed(
        self,
        *_,
    ):
        if not self.instruction:
            return

        value = self.offset_units_var.get()

        for enum_value in OffsetUnits:

            if enum_value.value == value:
                self.instruction.offset_units = (
                    enum_value
                )
                break

        self._recalculate()

    def _price_basis_changed(
        self,
        *_,
    ):
        if not self.instruction:
            return

        value = self.price_basis_var.get()

        for enum_value in PriceBasis:

            if enum_value.value == value:
                self.instruction.price_basis = (
                    enum_value
                )
                break

        self._recalculate()        

    def _quantity_changed(
        self,
        *_,
    ):

        if not self.instruction:
            return

        try:

            self.instruction.quantity_value = int(
                self.quantity_var.get()
            )

        except ValueError:

            return

    def _build_variables(self):

        self.symbol_var = tk.StringVar(
            value="-"
        )

        self.account_var = tk.StringVar()

        self.template_var = tk.StringVar()

        self.side_var = tk.StringVar()

        self.order_type_var = tk.StringVar()

        self.tif_var = tk.StringVar()

        self.quantity_type_var = tk.StringVar()

        self.quantity_var = tk.StringVar(
            value="100"
        )

        self.price_basis_var = tk.StringVar()

        self.offset_units_var = tk.StringVar()

        self.offset_value = tk.StringVar(
            value="0"
        )

        self.offset_value.trace_add(
            "write",
            self._offset_changed,
        )

        self.offset_units_var.trace_add(
            "write",
            self._offset_units_changed,
        )

        self.manual_price_var = tk.StringVar(
            value=""
        )

        self.manual_price_var.trace_add(
            "write",
            self._manual_price_changed,
        )

        self.review_var = tk.BooleanVar(
            value=True
        )

        self.price_basis_var.trace_add(
            "write",
            self._price_basis_changed,
        )

        self.quantity_var.trace_add(
            "write",
            self._quantity_changed,
        )

        #
        # Live prices
        #

        self.bid_var = tk.StringVar(
            value="-"
        )

        self.ask_var = tk.StringVar(
            value="-"
        )

        self.last_var = tk.StringVar(
            value="-"
        )


        #
        # Calculated price
        #

        self.base_price_var = tk.StringVar(
            value="-"
        )

        self.order_price_var = tk.StringVar(
            value="-"
        )


    # =========================================================
    # Construction
    # =========================================================

    def _build_ui(self):

        row = 0


        self._label_entry(
            "Symbol",
            self.symbol_var,
            row,
        )

        row += 1

        ttk.Label(
            self.frame,
            text="Account",
        ).grid(
            row=row,
            column=0,
            sticky="w",
        )

        self.account_box = ttk.Combobox(
            self.frame,
            textvariable=self.account_var,
            state="readonly",
        )

        self.account_box.bind(
            "<<ComboboxSelected>>",
            self._account_selected,
        )

        self.account_box.grid(
            row=row,
            column=1,
            sticky="ew",
        )

        row += 1

        ttk.Label(
            self.frame,
            text="Template",
        ).grid(
            row=row,
            column=0,
            sticky="w",
        )


        self.template_box = ttk.Combobox(
            self.frame,
            textvariable=
                self.template_var,
            state="readonly",
        )

        self.template_box.grid(
            row=row,
            column=1,
            sticky="ew",
        )

        self.template_box.bind(
            "<<ComboboxSelected>>",
            self._template_selected,
        )


        row += 1


        self._enum_box(
            "Side",
            self.side_var,
            [
                e.name
                for e in Side
            ],
            row,
        )

        row += 1


        self._enum_box(
            "Order Type",
            self.order_type_var,
            [
                e.name
                for e in OrderType
            ],
            row,
        )

        row += 1


        self._enum_box(
            "TIF",
            self.tif_var,
            [
                e.name
                for e in TimeInForce
            ],
            row,
        )

        row += 1


        self._enum_box(
            "Quantity Type",
            self.quantity_type_var,
            [
                e.value
                for e in QuantityType
            ],
            row,
        )

        row += 1


        self._label_entry(
            "Quantity",
            self.quantity_var,
            row,
        )

        row += 1


        self._enum_box(
            "Price Basis",
            self.price_basis_var,
            [
                e.value
                for e in PriceBasis
            ],
            row,
        )

        row += 1


        self._label_entry(
            "Offset",
            self.offset_value,
            row,
        )

        row += 1


        self._enum_box(
            "Offset Units",
            self.offset_units_var,
            [
                e.value
                for e in OffsetUnits
            ],
            row,
        )

        row += 1

        self._label_entry(
            "Manual Price",
            self.manual_price_var,
            row,
        )

        row += 1

        ttk.Checkbutton(
            self.frame,
            text="Review before send",
            variable=self.review_var,
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(5, 0),
        )

        row += 1


        #
        # Quote display
        #

        ttk.Separator(
            self.frame
        ).grid(
            row=row,
            columnspan=2,
            sticky="ew",
            pady=5,
        )

        row += 1


        self._label_display(
            "Bid",
            self.bid_var,
            row,
        )

        row += 1


        self._label_display(
            "Ask",
            self.ask_var,
            row,
        )

        row += 1


        self._label_display(
            "Last",
            self.last_var,
            row,
        )

        row += 1


        self._label_display(
            "Base Price",
            self.base_price_var,
            row,
        )

        row += 1


        self._label_display(
            "Order Price",
            self.order_price_var,
            row,
        )


        row += 1


        ttk.Button(
            self.frame,
            text="BUY",
            command=lambda:
                self._submit(Side.BUY),
        ).grid(
            row=row,
            column=0,
            pady=10,
        )


        ttk.Button(
            self.frame,
            text="SELL",
            command=lambda:
                self._submit(Side.SELL),
        ).grid(
            row=row,
            column=1,
            pady=10,
        )


    # =========================================================
    # Widgets
    # =========================================================

    def _label_entry(
        self,
        label,
        variable,
        row,
    ):

        ttk.Label(
            self.frame,
            text=label,
        ).grid(
            row=row,
            column=0,
            sticky="w",
        )

        ttk.Entry(
            self.frame,
            textvariable=variable,
        ).grid(
            row=row,
            column=1,
            sticky="ew",
        )


    def _label_display(
        self,
        label,
        variable,
        row,
    ):

        ttk.Label(
            self.frame,
            text=label,
        ).grid(
            row=row,
            column=0,
            sticky="w",
        )

        ttk.Label(
            self.frame,
            textvariable=variable,
        ).grid(
            row=row,
            column=1,
        )


    def _enum_box(
        self,
        label,
        variable,
        values,
        row,
    ):

        ttk.Label(
            self.frame,
            text=label,
        ).grid(
            row=row,
            column=0,
            sticky="w",
        )

        ttk.Combobox(
            self.frame,
            textvariable=variable,
            values=values,
            state="readonly",
        ).grid(
            row=row,
            column=1,
            sticky="ew",
        )


    # =========================================================
    # Public API
    # =========================================================

    def widget(self):

        return self.frame


    def set_symbol(
        self,
        symbol,
    ):
        self.selected_symbol = (
            symbol.upper()
            if symbol
            else None
        )

        self.symbol_var.set(
            self.selected_symbol or "-"
        )

        #
        # Clear stale quote display.
        #
        self.current_quote = None

        self.bid_var.set("-")
        self.ask_var.set("-")
        self.last_var.set("-")

        #
        # Clear stale calculated prices.
        #
        self.base_price_var.set("-")
        self.order_price_var.set("-")


        #
        # Update current instruction symbol.
        #
        if self.instruction:

            self.instruction.symbol = (
                self.selected_symbol
            )
            self.instruction.base_price = None
            self.instruction.order_price = None

    def get_symbol(self):

        return self.symbol_var.get()

    def set_accounts(self, accounts):
        print("PANEL set_accounts", accounts)
        self.accounts = accounts

        values = [
            account.display_name
            for account in accounts
        ]

        self.account_box["values"] = values

        if values:
            self.account_var.set(values[0])

            if self.instruction is not None:
                self.instruction.account = values[0]
                for account in accounts:
                    if account.display_name == values[0]:
                        self.instruction.account_hash = account.account_hash
                        break
                else:
                    self.instruction.account_hash = None

    def set_quote(
        self,
        quote,
    ):
        """
        Accept quote payload from Runtime.

        Runtime currently sends dictionaries:
            {
                symbol,
                bid,
                ask,
                last,
                volume
            }

        Future versions may send QuoteState objects.
        """


        if isinstance(quote, dict):

            bid = quote.get("bid")
            ask = quote.get("ask")
            last = quote.get("last")
            symbol = quote.get("symbol")
        else:
            symbol = quote.symbol
            bid = quote.bid
            ask = quote.ask
            last = quote.last

        #
        # Ignore quotes for symbols
        # not currently being traded.
        #

        if (
            self.selected_symbol
            and symbol
            and symbol.upper() != self.selected_symbol.upper()
        ):

            return

        self.current_quote = quote

        self.bid_var.set(
            self._fmt(bid)
        )

        self.ask_var.set(
            self._fmt(ask)
        )

        self.last_var.set(
            self._fmt(last)
        )


        if self.instruction:

            self.instruction.bid = bid

            self.instruction.ask = ask

            self.instruction.last = last

            PriceCalculator.apply(
                self.instruction
            )

            self.base_price_var.set(
                self._fmt(
                    self.instruction.base_price
                )
            )

            self.order_price_var.set(
                self._fmt(
                    self.instruction.order_price
                )
            )


    def clear_quote(self):

        self.current_quote = None

        self.bid_var.set("-")

        self.ask_var.set("-")

        self.last_var.set("-")

        self.base_price_var.set("-")

        self.order_price_var.set("-")


        if self.instruction:

            self.instruction.bid = None
            self.instruction.ask = None
            self.instruction.last = None

    # =========================================================
    # Template handling
    # =========================================================

    def load_templates(self):

        if not self.trading_config:

            return


        self.template_box["values"] = (
            list(
                self.trading_config.templates.keys()
            )
        )


    def _template_selected(
        self,
        event=None,
    ):

        name = self.template_var.get()

        if not name:

            return


        if not self.trade_instruction_factory:

            raise RuntimeError(
                "TradeInstructionFactory missing."
            )


        symbol = self.get_symbol()


        if symbol == "-":

            messagebox.showwarning(
                "Missing Symbol",
                "Select a symbol before choosing a template.",
            )

            return

        quote = self.current_quote

        if quote is None and self.get_quote:
            quote = self.get_quote(symbol)

        self.instruction = (
            self.trade_instruction_factory.create(
                template_name=name,
                symbol=symbol,
                quote=quote,
            )
        )


        self._display_instruction()



    # =========================================================
    # Display
    # =========================================================

    def _account_selected(
        self,
        event=None,
    ):
        if not self.instruction:
            return

        selected_name = self.account_var.get()

        if not self.accounts:
            self.instruction.account_hash = None
            return

        for account in self.accounts:
            if account.display_name == selected_name:
                self.instruction.account = account.display_name
                self.instruction.account_hash = account.account_hash
                return

        self.instruction.account_hash = None

    @staticmethod
    def _build_debug_payload(
        instruction: TradeInstruction,
    ):
        from trading_app.services.order_factory import OrderFactory

        request = OrderFactory().create(instruction)
        payload = request.to_schwab_order_spec()

        return {
            "request": request,
            "account_hash": request.account_hash,
            "schwab_payload": payload,
        }

    def apply_template_to_panel(
        self,
        template_name: str,
        *,
        quote=None,
        side=None,
        quantity=None,
        review_before_send=None,
    ) -> TradeInstruction:
        if not self.trade_instruction_factory:
            raise RuntimeError("TradeInstructionFactory missing.")

        if not self.selected_symbol:
            raise ValueError("No symbol selected.")

        instruction = self.trade_instruction_factory.create(
            template_name=template_name,
            symbol=self.selected_symbol,
            quote=quote,
        )

        if side is not None:
            instruction.side = side

        if quantity is not None:
            instruction.quantity_value = int(quantity)

        if review_before_send is not None:
            instruction.review_before_send = review_before_send

        if self.accounts:
            current_account = self.account_var.get()
            if current_account:
                instruction.account = current_account
                for account in self.accounts:
                    if account.display_name == current_account:
                        instruction.account_hash = account.account_hash
                        break
                else:
                    instruction.account_hash = None

        self.instruction = instruction
        self._display_instruction()
        self._recalculate()
        return instruction

    def _display_instruction(self):

        i = self.instruction

        self.account_var.set(
            i.account
        )

        self.template_var.set(
            i.template_name
        )

        self.side_var.set(
            i.side.name
        )

        self.order_type_var.set(
            i.order_type.name
        )

        self.tif_var.set(
            i.tif.name
        )

        self.quantity_type_var.set(
            i.quantity_type.value
        )

        self.quantity_var.set(
            str(i.quantity)
        )

        self.price_basis_var.set(
            i.price_basis.value
        )

        self.offset_units_var.set(
            i.offset_units.value
        )

        self.offset_value.set(
            str(i.offset_value)
        )

        if i.manual_order_price is None:
            self.manual_price_var.set("")
        else:
            self.manual_price_var.set(
                str(i.manual_order_price)
            )

        self.review_var.set(
            i.review_before_send
        )

        self.base_price_var.set(
            self._fmt(i.base_price)
        )

        self.order_price_var.set(
            self._fmt(i.order_price)
        )


    # =========================================================
    # Submit
    # =========================================================

    def _submit(
        self,
        side,
    ):

        if not self.instruction:

            messagebox.showwarning(
                "No Instruction",
                "Select a template first.",
            )

            return

        self.instruction.account = (
            self.account_var.get()
        )

        self._account_selected()

        self.instruction.side = side

        self.instruction.quantity_value = int(
            self.quantity_var.get()
        )

        self.instruction.review_before_send = bool(
            self.review_var.get()
        )

        manual_value = self.manual_price_var.get().strip()

        if manual_value:
            try:
                self.instruction.manual_order_price = float(
                    manual_value
                )
            except ValueError:
                messagebox.showerror(
                    "Invalid Price",
                    "Manual price must be numeric.",
                )
                return
        else:
            self.instruction.manual_order_price = None

        self._recalculate()

        debug_payload = self._build_debug_payload(self.instruction)
        print(
            "SCHWAB ORDER DEBUG",
            pprint.pformat(debug_payload),
            flush=True,
        )

        if self.instruction.review_before_send:
            review_text = (
                f"Symbol: {self.instruction.symbol}\n"
                f"Side: {self.instruction.side.name}\n"
                f"Order Type: {self.instruction.order_type.name}\n"
                f"Quantity: {self.instruction.quantity}\n"
                f"Price: {self._fmt(self.instruction.order_price)}\n"
                f"TIF: {self.instruction.tif.name}"
            )

            if not messagebox.askyesno(
                "Review Order",
                "Send this order?\n\n"
                + review_text,
            ):
                return

        if self.on_submit:

            self.on_submit(
                self.instruction
            )


    @staticmethod
    def _fmt(value):

        if value is None:

            return "-"

        return f"{value:.2f}"