"""
gui/status_bar.py

StatusBar widget.

Responsibilities:
    - Display application status information
    - Provide update methods for the application layer

Non-responsibilities:
    - Networking
    - Broker connectivity
    - Market state management
    - Event handling
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from datetime import datetime

class StatusBar:
    """
    Bottom application status bar.

    Public interface:

        set_connection(state)
        set_market_state(state)
        set_message(message)
        clear_message()

    """

    def __init__(
        self,
        parent: tk.Widget,
        on_simulation_changed=None,
    ):

        self.parent = parent

        self.frame = ttk.Frame(
            parent,
            relief=tk.SUNKEN,
        )

        self.simulation_mode = tk.BooleanVar(value=True)

        self.connection_var = tk.StringVar(
            value="Disconnected"
        )

        self.market_var = tk.StringVar(
            value="Market Closed"
        )

        self.message_var = tk.StringVar(
            value=""
        )

        self.time_var = tk.StringVar(
            value=""
        )

        self.sim_callback = on_simulation_changed

        self.style = ttk.Style()
        
        self._build_ui()

        self.update_time()

    
    def _simulation_clicked(self):
        if self.sim_callback:
            self.sim_callback(self.simulation_mode.get())

        
    # -------------------------------------------------------------
    # Construction
    # -------------------------------------------------------------

    def set_execution_mode(self, simulation):
        
        if simulation:
            self.simulation_mode.set(True) 
            self.style.configure(
                "Simulation.TLabel",
                foreground="green"
            )
            self.status_execution.configure(
                text="SIMULATION",
                style="Simulation.TLabel"
            )
        else:
            self.simulation_mode.set(False) 
            self.style.configure(
                "Live.TLabel",
                foreground="red"
            )
            self.status_execution.configure(
                text="LIVE",
                style="Live.TLabel"
            )

    def _build_ui(self):

        self.chk_simulation = ttk.Checkbutton(
            self.frame,
            text="Simulation",
            variable=self.simulation_mode,
            command=self._simulation_clicked
        )

        self.chk_simulation.pack(side=tk.LEFT, padx=(20, 0))
        
        self.style.configure(
                "Simulation.TLabel",
                foreground="green"
            )
        self.style.configure(
                "Live.TLabel",
                foreground="red"
            )
        self.status_execution = ttk.Label(
            self.frame,
            text="SIMULATION",
            style="Simulation.TLabel",
            width=12
        )

        self.status_execution.pack(side=tk.LEFT, padx=(20, 0))

        
        ttk.Separator(
            self.frame,
            orient=tk.VERTICAL,
        ).pack(
            side=tk.LEFT,
            fill=tk.Y,
            padx=5,
        )

        ttk.Label(
            self.frame,
            text="Connection:",
        ).pack(
            side=tk.LEFT,
            padx=5,
        )


        ttk.Label(
            self.frame,
            textvariable=self.connection_var,
            width=15,
        ).pack(
            side=tk.LEFT,
        )


        ttk.Separator(
            self.frame,
            orient=tk.VERTICAL,
        ).pack(
            side=tk.LEFT,
            fill=tk.Y,
            padx=5,
        )


        ttk.Label(
            self.frame,
            text="Market:",
        ).pack(
            side=tk.LEFT,
            padx=5,
        )


        ttk.Label(
            self.frame,
            textvariable=self.market_var,
            width=15,
        ).pack(
            side=tk.LEFT,
        )


        ttk.Label(
            self.frame,
            textvariable=self.message_var,
        ).pack(
            side=tk.LEFT,
            expand=True,
            padx=10,
        )


        ttk.Label(
            self.frame,
            textvariable=self.time_var,
            width=10,
        ).pack(
            side=tk.RIGHT,
            padx=5,
        )


    # -------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------

    def widget(self):

        return self.frame


    def set_connection(
        self,
        state: str,
    ):

        self.connection_var.set(
            state
        )


    def set_market_state(
        self,
        state: str,
    ):

        self.market_var.set(
            state
        )


    def set_message(
        self,
        message: str,
    ):

        self.message_var.set(
            message
        )


    def clear_message(self):

        self.message_var.set(
            ""
        )


    # -------------------------------------------------------------
    # Internal clock
    # -------------------------------------------------------------

    def update_time(self):

        now = datetime.now()

        self.time_var.set(
            now.strftime(
                "%H:%M:%S"
            )
        )

        #
        # GUI-owned timer only.
        #
        # This does not touch
        # market/application state.
        #

        self.frame.after(
            1000,
            self.update_time,
        )