"""
GUI theme definitions and styling.

This module contains the centralized visual configuration for the
Trading Terminal GUI.

Responsibilities:
    - Define the dark-mode color palette.
    - Configure ttk styles.
    - Provide styling helpers for classic Tk widgets.
    - Provide styling helpers for menus and Treeviews.

Non-responsibilities:
    - Creating application widgets.
    - Managing application state.
    - Trading logic.
    - Market data handling.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


# ----------------------------------------------------------------------
# Dark theme colors
# ----------------------------------------------------------------------

DARK = {
    # Main application
    "bg": "#1e1e1e",

    # Panels / frames
    "surface": "#252526",
    "surface2": "#2d2d30",

    # Borders / separators
    "border": "#3f3f46",

    # Normal text
    "fg": "#d4d4d4",
    "fg_muted": "#9d9d9d",

    # Text selection
    "select_bg": "#264f78",
    "select_fg": "#ffffff",

    # Input controls
    "entry_bg": "#181818",
    "entry_fg": "#d4d4d4",

    # Disabled controls
    "disabled_bg": "#252525",
    "disabled_fg": "#666666",

    # Table
    "table_bg": "#181818",
    "table_fg": "#d4d4d4",
    "table_heading_bg": "#2d2d30",
    "table_heading_fg": "#d4d4d4",

    # Trading/market data colors
    "positive": "#4ec9b0",
    "negative": "#f44747",
    "neutral": "#d4d4d4",

    # Focus
    "focus": "#007acc",

    # Scrollbars
    "scrollbar_bg": "#2d2d30",
    "scrollbar_trough": "#1e1e1e",

    # Warning / status colors
    "warning": "#dcdcaa",
    "error": "#f44747",
    "info": "#569cd6",
}


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def get_dark_colors() -> dict[str, str]:
    """
    Return a copy of the dark-theme color palette.

    Returning a copy prevents callers from accidentally modifying the
    global DARK dictionary.
    """
    return DARK.copy()


def configure_dark_theme(root: tk.Tk) -> ttk.Style:
    """
    Configure the application's complete ttk dark theme.

    This should be called once, immediately after creating the Tk root
    and before constructing the application's widgets.

    Example:

        self.root = tk.Tk()
        configure_dark_theme(self.root)

    Parameters
    ----------
    root:
        The application's Tk root window.

    Returns
    -------
    ttk.Style
        The configured ttk Style object.
    """

    style = ttk.Style(root)

    # --------------------------------------------------------------
    # Select a theme that allows us to control colors reliably.
    # --------------------------------------------------------------

    try:
        style.theme_use("clam")
    except tk.TclError:
        # "clam" is normally available, but don't prevent the
        # application from starting if it isn't.
        pass

    # --------------------------------------------------------------
    # Root window
    # --------------------------------------------------------------

    root.configure(
        background=DARK["bg"]
    )

    # --------------------------------------------------------------
    # Base ttk configuration
    # --------------------------------------------------------------

    style.configure(
        ".",
        background=DARK["bg"],
        foreground=DARK["fg"],
        bordercolor=DARK["border"],
        lightcolor=DARK["border"],
        darkcolor=DARK["border"],
    )

    # --------------------------------------------------------------
    # Frames
    # --------------------------------------------------------------

    style.configure(
        "TFrame",
        background=DARK["bg"],
    )

    # --------------------------------------------------------------
    # Labels
    # --------------------------------------------------------------

    style.configure(
        "TLabel",
        background=DARK["bg"],
        foreground=DARK["fg"],
    )

    # --------------------------------------------------------------
    # LabelFrame
    # --------------------------------------------------------------

    style.configure(
        "TLabelFrame",
        background=DARK["bg"],
        foreground=DARK["fg"],
        bordercolor=DARK["border"],
        lightcolor=DARK["border"],
        darkcolor=DARK["border"],
    )

    style.configure(
        "TLabelFrame.Label",
        background=DARK["bg"],
        foreground=DARK["fg"],
    )

    # --------------------------------------------------------------
    # Buttons
    # --------------------------------------------------------------

    style.configure(
        "TButton",
        background=DARK["surface2"],
        foreground=DARK["fg"],
        bordercolor=DARK["border"],
        lightcolor=DARK["border"],
        darkcolor=DARK["border"],
        padding=(8, 4),
    )

    style.map(
        "TButton",
        background=[
            ("pressed", DARK["select_bg"]),
            ("active", DARK["select_bg"]),
            ("disabled", DARK["disabled_bg"]),
        ],
        foreground=[
            ("disabled", DARK["disabled_fg"]),
            ("active", DARK["select_fg"]),
        ],
        bordercolor=[
            ("focus", DARK["focus"]),
        ],
    )

    # --------------------------------------------------------------
    # Entry
    # --------------------------------------------------------------

    style.configure(
        "TEntry",
        background=DARK["entry_bg"],
        foreground=DARK["entry_fg"],
        fieldbackground=DARK["entry_bg"],
        bordercolor=DARK["border"],
        lightcolor=DARK["border"],
        darkcolor=DARK["border"],
        insertcolor=DARK["fg"],
    )

    style.map(
        "TEntry",
        fieldbackground=[
            ("disabled", DARK["disabled_bg"]),
        ],
        foreground=[
            ("disabled", DARK["disabled_fg"]),
        ],
        bordercolor=[
            ("focus", DARK["focus"]),
        ],
    )

    # --------------------------------------------------------------
    # Combobox
    # --------------------------------------------------------------

    configure_combobox_style(style)

    # --------------------------------------------------------------
    # Checkbutton
    # --------------------------------------------------------------

    style.configure(
        "TCheckbutton",
        background=DARK["bg"],
        foreground=DARK["fg"],
    )

    style.map(
        "TCheckbutton",
        background=[
            ("active", DARK["bg"]),
        ],
        foreground=[
            ("disabled", DARK["disabled_fg"]),
        ],
    )

    # --------------------------------------------------------------
    # Radiobutton
    # --------------------------------------------------------------

    style.configure(
        "TRadiobutton",
        background=DARK["bg"],
        foreground=DARK["fg"],
    )

    style.map(
        "TRadiobutton",
        background=[
            ("active", DARK["bg"]),
        ],
        foreground=[
            ("disabled", DARK["disabled_fg"]),
        ],
    )

    # --------------------------------------------------------------
    # Spinbox
    # --------------------------------------------------------------

    style.configure(
        "TSpinbox",
        background=DARK["entry_bg"],
        foreground=DARK["entry_fg"],
        fieldbackground=DARK["entry_bg"],
        bordercolor=DARK["border"],
        lightcolor=DARK["border"],
        darkcolor=DARK["border"],
        arrowcolor=DARK["fg"],
    )

    style.map(
        "TSpinbox",
        fieldbackground=[
            ("disabled", DARK["disabled_bg"]),
        ],
        foreground=[
            ("disabled", DARK["disabled_fg"]),
        ],
        bordercolor=[
            ("focus", DARK["focus"]),
        ],
    )

    # --------------------------------------------------------------
    # Scale
    # --------------------------------------------------------------

    style.configure(
        "TScale",
        background=DARK["bg"],
        troughcolor=DARK["entry_bg"],
    )

    # --------------------------------------------------------------
    # Progressbar
    # --------------------------------------------------------------

    style.configure(
        "TProgressbar",
        background=DARK["select_bg"],
        troughcolor=DARK["entry_bg"],
        bordercolor=DARK["border"],
        lightcolor=DARK["select_bg"],
        darkcolor=DARK["select_bg"],
    )

    # --------------------------------------------------------------
    # Separators
    # --------------------------------------------------------------

    style.configure(
        "TSeparator",
        background=DARK["border"],
    )

    # --------------------------------------------------------------
    # Treeview
    # --------------------------------------------------------------

    configure_treeview_style(style)

    # --------------------------------------------------------------
    # Scrollbars
    # --------------------------------------------------------------

    style.configure(
        "Vertical.TScrollbar",
        background=DARK["scrollbar_bg"],
        troughcolor=DARK["scrollbar_trough"],
        bordercolor=DARK["border"],
        arrowcolor=DARK["fg"],
    )

    style.configure(
        "Horizontal.TScrollbar",
        background=DARK["scrollbar_bg"],
        troughcolor=DARK["scrollbar_trough"],
        bordercolor=DARK["border"],
        arrowcolor=DARK["fg"],
    )

    return style


# ----------------------------------------------------------------------
# Specialized ttk styles
# ----------------------------------------------------------------------

def configure_treeview_style(style: ttk.Style) -> None:
    """
    Configure Treeview and Treeview heading styles.

    Used by QuoteTable and MomentumTable.
    """

    style.configure(
        "Dark.Treeview",
        background=DARK["table_bg"],
        foreground=DARK["table_fg"],
        fieldbackground=DARK["table_bg"],
        bordercolor=DARK["border"],
        lightcolor=DARK["border"],
        darkcolor=DARK["border"],
        rowheight=24,
    )

    style.map(
        "Dark.Treeview",
        background=[
            ("selected", DARK["select_bg"]),
        ],
        foreground=[
            ("selected", DARK["select_fg"]),
        ],
    )

    style.configure(
        "Dark.Treeview.Heading",
        background=DARK["table_heading_bg"],
        foreground=DARK["table_heading_fg"],
        bordercolor=DARK["border"],
        lightcolor=DARK["border"],
        darkcolor=DARK["border"],
        relief="flat",
        padding=(5, 4),
    )

    style.map(
        "Dark.Treeview.Heading",
        background=[
            ("active", DARK["select_bg"]),
        ],
        foreground=[
            ("active", DARK["select_fg"]),
        ],
    )


def configure_combobox_style(style: ttk.Style) -> None:
    """
    Configure ttk.Combobox for dark mode.
    """

    style.configure(
        "TCombobox",
        background=DARK["surface2"],
        foreground=DARK["fg"],
        fieldbackground=DARK["entry_bg"],
        bordercolor=DARK["border"],
        lightcolor=DARK["border"],
        darkcolor=DARK["border"],
        arrowcolor=DARK["fg"],
    )

    style.map(
        "TCombobox",
        fieldbackground=[
            ("readonly", DARK["entry_bg"]),
            ("disabled", DARK["disabled_bg"]),
        ],
        foreground=[
            ("readonly", DARK["fg"]),
            ("disabled", DARK["disabled_fg"]),
        ],
        background=[
            ("readonly", DARK["surface2"]),
            ("disabled", DARK["disabled_bg"]),
        ],
        bordercolor=[
            ("focus", DARK["focus"]),
        ],
    )


# ----------------------------------------------------------------------
# Classic Tk widget helpers
# ----------------------------------------------------------------------

def configure_menu(menu: tk.Menu) -> None:
    """
    Apply the dark theme to a classic Tk Menu.

    ttk does not provide a themed Menu widget, so normal tk.Menu
    instances need their colors configured explicitly.

    Example:

        self.context_menu = tk.Menu(self.tree, tearoff=False)
        configure_menu(self.context_menu)
    """

    menu.configure(
        background=DARK["surface"],
        foreground=DARK["fg"],
        activebackground=DARK["select_bg"],
        activeforeground=DARK["select_fg"],
        disabledforeground=DARK["disabled_fg"],
        borderwidth=0,
        relief="flat",
    )


def configure_tk_widget(widget: tk.Widget) -> None:
    """
    Apply appropriate dark-mode colors to a classic Tk widget.

    This is useful for widgets that do not have a ttk equivalent,
    such as tk.Menu, tk.Text, tk.Listbox, and tk.Entry.

    The function intentionally uses isinstance() checks so that it
    does not attempt to apply unsupported options to arbitrary
    Tk widgets.
    """

    if isinstance(widget, tk.Menu):
        configure_menu(widget)
        return

    if isinstance(widget, tk.Entry):
        widget.configure(
            background=DARK["entry_bg"],
            foreground=DARK["entry_fg"],
            insertbackground=DARK["fg"],
            selectbackground=DARK["select_bg"],
            selectforeground=DARK["select_fg"],
        )
        return

    if isinstance(widget, tk.Text):
        widget.configure(
            background=DARK["entry_bg"],
            foreground=DARK["entry_fg"],
            insertbackground=DARK["fg"],
            selectbackground=DARK["select_bg"],
            selectforeground=DARK["select_fg"],
        )
        return

    if isinstance(widget, tk.Listbox):
        widget.configure(
            background=DARK["entry_bg"],
            foreground=DARK["entry_fg"],
            selectbackground=DARK["select_bg"],
            selectforeground=DARK["select_fg"],
        )
        return

    if isinstance(widget, tk.Label):
        widget.configure(
            background=DARK["bg"],
            foreground=DARK["fg"],
        )
        return

    if isinstance(widget, tk.Frame):
        widget.configure(
            background=DARK["bg"],
        )


def configure_tk_menu(
    parent: tk.Widget,
    *,
    tearoff: bool = False,
) -> tk.Menu:
    """
    Create and configure a dark Tk Menu.

    Convenience function for creating context menus.

    Example:

        self.context_menu = configure_tk_menu(self.tree)
        self.context_menu.add_command(
            label="Delete",
            command=self._delete_context_symbol,
        )

    Returns
    -------
    tk.Menu
        The configured menu.
    """

    menu = tk.Menu(
        parent,
        tearoff=tearoff,
    )

    configure_menu(menu)

    return menu


# ----------------------------------------------------------------------
# Recursive widget helper
# ----------------------------------------------------------------------

def apply_dark_theme_to_widgets(widget: tk.Widget) -> None:
    """
    Recursively apply dark styling to classic Tk widgets.

    This is primarily a compatibility helper.

    ttk widgets should rely on configure_dark_theme() and ttk.Style
    rather than having their colors manually configured here.

    Parameters
    ----------
    widget:
        Root widget from which the widget hierarchy should be walked.
    """

    configure_tk_widget(widget)

    for child in widget.winfo_children():
        apply_dark_theme_to_widgets(child)