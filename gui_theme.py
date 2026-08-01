"""Identité visuelle sobre de l'interface Tkinter."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class Colors:
    BACKGROUND = "#F3F6FA"
    SURFACE = "#FFFFFF"
    SIDEBAR = "#17243A"
    SIDEBAR_HOVER = "#243754"
    PRIMARY = "#2463A7"
    PRIMARY_DARK = "#194D86"
    TEXT = "#172033"
    MUTED = "#637083"
    BORDER = "#D9E1EA"
    SUCCESS = "#22845D"
    SUCCESS_BG = "#E8F5EF"
    WARNING = "#B56B00"
    WARNING_BG = "#FFF3DA"
    DANGER = "#B83A43"
    DANGER_BG = "#FDEBED"
    INFO = "#2A6FAD"
    INFO_BG = "#E8F2FB"


STATUS_COLORS = {
    "CONFORME": (Colors.SUCCESS, Colors.SUCCESS_BG),
    "A_CONTROLER": (Colors.WARNING, Colors.WARNING_BG),
    "REJETE": (Colors.DANGER, Colors.DANGER_BG),
    "SANS_CONTROLE": (Colors.INFO, Colors.INFO_BG),
    "ARCHIVE": (Colors.MUTED, "#E9EDF2"),
    "DISPONIBLE": (Colors.SUCCESS, Colors.SUCCESS_BG),
    "EN_UTILISATION": (Colors.INFO, Colors.INFO_BG),
    "SURVEILLANCE": (Colors.WARNING, Colors.WARNING_BG),
    "MAINTENANCE": (Colors.WARNING, Colors.WARNING_BG),
    "HORS_SERVICE": (Colors.DANGER, Colors.DANGER_BG),
    "OUVERT": (Colors.DANGER, Colors.DANGER_BG),
    "EN_COURS": (Colors.WARNING, Colors.WARNING_BG),
    "RESOLU": (Colors.SUCCESS, Colors.SUCCESS_BG),
    "CLOTURE": (Colors.MUTED, "#E9EDF2"),
    "NOUVELLE": (Colors.DANGER, Colors.DANGER_BG),
    "ACQUITTEE": (Colors.INFO, Colors.INFO_BG),
    "IGNOREE": (Colors.MUTED, "#E9EDF2"),
    "RESOLUE": (Colors.SUCCESS, Colors.SUCCESS_BG),
}


def configure_theme(root: tk.Tk) -> ttk.Style:
    """Configure uniquement des styles ttk standard et portables."""

    root.configure(background=Colors.BACKGROUND)
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    default_font = ("Segoe UI", 10)
    root.option_add("*Font", default_font)
    root.option_add("*TCombobox*Listbox.font", default_font)

    style.configure("TFrame", background=Colors.BACKGROUND)
    style.configure("Surface.TFrame", background=Colors.SURFACE)
    style.configure(
        "TLabel", background=Colors.BACKGROUND, foreground=Colors.TEXT, padding=0
    )
    style.configure(
        "Surface.TLabel", background=Colors.SURFACE, foreground=Colors.TEXT
    )
    style.configure(
        "Title.TLabel",
        font=("Segoe UI Semibold", 22),
        background=Colors.BACKGROUND,
        foreground=Colors.TEXT,
    )
    style.configure(
        "Subtitle.TLabel",
        font=("Segoe UI", 10),
        background=Colors.BACKGROUND,
        foreground=Colors.MUTED,
    )
    style.configure(
        "Section.TLabel",
        font=("Segoe UI Semibold", 13),
        background=Colors.SURFACE,
        foreground=Colors.TEXT,
    )
    style.configure(
        "KpiValue.TLabel",
        font=("Segoe UI Semibold", 22),
        background=Colors.SURFACE,
        foreground=Colors.TEXT,
    )
    style.configure(
        "KpiCaption.TLabel",
        font=("Segoe UI", 8),
        background=Colors.SURFACE,
        foreground=Colors.MUTED,
    )

    style.configure(
        "TButton",
        background=Colors.SURFACE,
        foreground=Colors.TEXT,
        bordercolor=Colors.BORDER,
        padding=(12, 8),
        relief="flat",
    )
    style.map("TButton", background=[("active", "#E9EFF6")])
    style.configure(
        "Primary.TButton",
        background=Colors.PRIMARY,
        foreground="#FFFFFF",
        bordercolor=Colors.PRIMARY,
        font=("Segoe UI Semibold", 10),
    )
    style.map(
        "Primary.TButton",
        background=[("active", Colors.PRIMARY_DARK), ("disabled", "#9CB6D0")],
        foreground=[("disabled", "#EEF3F8")],
    )
    style.configure(
        "Danger.TButton",
        background=Colors.DANGER_BG,
        foreground=Colors.DANGER,
        bordercolor=Colors.DANGER_BG,
    )
    style.map("Danger.TButton", background=[("active", "#F8D7DB")])
    style.configure(
        "Nav.TButton",
        background=Colors.SIDEBAR,
        foreground="#DCE6F2",
        borderwidth=0,
        anchor="w",
        padding=(18, 11),
        font=("Segoe UI", 10),
    )
    style.map(
        "Nav.TButton",
        background=[("active", Colors.SIDEBAR_HOVER)],
        foreground=[("active", "#FFFFFF")],
    )
    style.configure(
        "Active.Nav.TButton",
        background=Colors.PRIMARY,
        foreground="#FFFFFF",
        borderwidth=0,
        anchor="w",
        padding=(18, 11),
        font=("Segoe UI Semibold", 10),
    )

    style.configure(
        "Treeview",
        background=Colors.SURFACE,
        fieldbackground=Colors.SURFACE,
        foreground=Colors.TEXT,
        rowheight=34,
        bordercolor=Colors.BORDER,
        borderwidth=1,
    )
    style.configure(
        "Treeview.Heading",
        background="#EAF0F6",
        foreground=Colors.TEXT,
        font=("Segoe UI Semibold", 9),
        padding=(6, 8),
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", "#D8E8F7")],
        foreground=[("selected", Colors.TEXT)],
    )
    style.configure(
        "TEntry", fieldbackground=Colors.SURFACE, bordercolor=Colors.BORDER, padding=7
    )
    style.configure(
        "TCombobox",
        fieldbackground=Colors.SURFACE,
        background=Colors.SURFACE,
        bordercolor=Colors.BORDER,
        padding=6,
    )
    style.configure("TSeparator", background=Colors.BORDER)
    return style


def center_window(window: tk.Toplevel, width: int, height: int) -> None:
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")
