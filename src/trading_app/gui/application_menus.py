"""
gui/application_menus.py

Application menu definitions.

Responsibilities:
    - Build Tk menus
    - Invoke callbacks supplied by application layer

Non-responsibilities:
    - Broker communication
    - Trading logic
    - Application state management
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional


class ApplicationMenus:
    """
    Main application menu bar.

    Callbacks are injected by the application composer.

    Example:

        menus = ApplicationMenus(
            root,
            on_connect=self.connect,
            on_disconnect=self.disconnect,
            on_exit=self.shutdown,
        )

    """

    def __init__(
        self,
        root: tk.Tk,
        *,
        on_connect: Optional[Callable] = None,
        on_disconnect: Optional[Callable] = None,
        on_exit: Optional[Callable] = None,
        on_cancel_orders: Optional[Callable] = None,
        on_flatten_position: Optional[Callable] = None,
        on_about: Optional[Callable] = None,
    ):

        self.root = root

        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_exit = on_exit

        self.on_cancel_orders = (
            on_cancel_orders
        )

        self.on_flatten_position = (
            on_flatten_position
        )

        self.on_about = on_about


        self.menu = tk.Menu(
            root
        )

        self._build()


        root.configure(
            menu=self.menu
        )


    # -------------------------------------------------------------
    # Construction
    # -------------------------------------------------------------

    def _build(self):

        self._build_file_menu()
        self._build_trading_menu()
        self._build_view_menu()
        self._build_help_menu()


    def _build_file_menu(self):

        menu = tk.Menu(
            self.menu,
            tearoff=False,
        )


        menu.add_command(
            label="Connect",
            command=self._connect,
        )


        menu.add_command(
            label="Disconnect",
            command=self._disconnect,
        )


        menu.add_separator()


        menu.add_command(
            label="Exit",
            command=self._exit,
        )


        self.menu.add_cascade(
            label="File",
            menu=menu,
        )


    def _build_trading_menu(self):

        menu = tk.Menu(
            self.menu,
            tearoff=False,
        )


        menu.add_command(
            label="Cancel All Orders",
            command=self._cancel_orders,
        )


        menu.add_command(
            label="Flatten Position",
            command=self._flatten_position,
        )


        self.menu.add_cascade(
            label="Trading",
            menu=menu,
        )


    def _build_view_menu(self):

        menu = tk.Menu(
            self.menu,
            tearoff=False,
        )


        #
        # Reserved for:
        #
        # - dark mode
        # - layout switching
        # - column visibility
        #

        menu.add_command(
            label="Refresh",
        )


        self.menu.add_cascade(
            label="View",
            menu=menu,
        )


    def _build_help_menu(self):

        menu = tk.Menu(
            self.menu,
            tearoff=False,
        )


        menu.add_command(
            label="About",
            command=self._about,
        )


        self.menu.add_cascade(
            label="Help",
            menu=menu,
        )


    # -------------------------------------------------------------
    # Callback wrappers
    # -------------------------------------------------------------

    def _connect(self):

        if self.on_connect:
            self.on_connect()


    def _disconnect(self):

        if self.on_disconnect:
            self.on_disconnect()


    def _exit(self):

        if self.on_exit:
            self.on_exit()


    def _cancel_orders(self):

        if self.on_cancel_orders:
            self.on_cancel_orders()


    def _flatten_position(self):

        if self.on_flatten_position:
            self.on_flatten_position()


    def _about(self):

        if self.on_about:
            self.on_about()