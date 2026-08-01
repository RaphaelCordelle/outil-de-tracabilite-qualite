"""Composants graphiques réutilisables."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable, Optional, Sequence

from gui_theme import Colors, STATUS_COLORS


class Page(ttk.Frame):
    """Base commune des pages avec titre, description et zone de contenu."""

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        description: str,
        actions: Sequence[tuple[str, Callable[[], None], str]] = (),
    ) -> None:
        super().__init__(parent, padding=(28, 22))
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 18))
        text = ttk.Frame(header)
        text.pack(side="left", fill="x", expand=True)
        ttk.Label(text, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(text, text=description, style="Subtitle.TLabel").pack(
            anchor="w", pady=(4, 0)
        )
        if actions:
            buttons = ttk.Frame(header)
            buttons.pack(side="right")
            for label, command, style in actions:
                ttk.Button(buttons, text=label, command=command, style=style).pack(
                    side="left", padx=(8, 0)
                )
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True)

    def refresh(self) -> None:
        """Recharge les données affichées par la page."""


class Surface(ttk.Frame):
    def __init__(self, parent: tk.Misc, padding: int = 16, **kwargs: object) -> None:
        super().__init__(parent, style="Surface.TFrame", padding=padding, **kwargs)


class KpiCard(tk.Frame):
    def __init__(
        self, parent: tk.Misc, caption: str, value: str, accent: str = Colors.PRIMARY
    ) -> None:
        super().__init__(
            parent,
            background=Colors.SURFACE,
            highlightbackground=Colors.BORDER,
            highlightthickness=1,
        )
        tk.Frame(self, background=accent, height=4).pack(fill="x")
        content = ttk.Frame(self, style="Surface.TFrame", padding=(12, 11))
        content.pack(fill="both", expand=True)
        self.value_label = ttk.Label(content, text=value, style="KpiValue.TLabel")
        self.value_label.pack(anchor="w")
        ttk.Label(
            content,
            text=caption,
            style="KpiCaption.TLabel",
            wraplength=135,
        ).pack(anchor="w", pady=(2, 0))

    def set_value(self, value: object) -> None:
        self.value_label.configure(text=str(value))


class StatusLabel(tk.Label):
    def __init__(self, parent: tk.Misc, status: str) -> None:
        foreground, background = STATUS_COLORS.get(
            status, (Colors.MUTED, "#E9EDF2")
        )
        super().__init__(
            parent,
            text=status.replace("_", " "),
            foreground=foreground,
            background=background,
            font=("Segoe UI Semibold", 9),
            padx=10,
            pady=4,
        )


class DataTable(ttk.Frame):
    """Treeview avec défilement, colonnes configurables et lignes colorées."""

    def __init__(
        self,
        parent: tk.Misc,
        columns: Sequence[tuple[str, str, int, str]],
        *,
        height: int = 14,
        horizontal_scroll: bool = True,
    ) -> None:
        super().__init__(parent, style="Surface.TFrame")
        identifiers = [column[0] for column in columns]
        self.tree = ttk.Treeview(
            self, columns=identifiers, show="headings", height=height, selectmode="browse"
        )
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(
            yscrollcommand=vertical.set
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        if horizontal_scroll:
            horizontal = ttk.Scrollbar(
                self, orient="horizontal", command=self.tree.xview
            )
            self.tree.configure(xscrollcommand=horizontal.set)
            horizontal.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        for identifier, heading, width, anchor in columns:
            self.tree.heading(identifier, text=heading)
            self.tree.column(
                identifier, width=width, minwidth=60, anchor=anchor, stretch=True
            )
        self.tree.tag_configure("CONFORME", foreground=Colors.SUCCESS)
        self.tree.tag_configure("A_CONTROLER", foreground=Colors.WARNING)
        self.tree.tag_configure("REJETE", foreground=Colors.DANGER)
        self.tree.tag_configure("SANS_CONTROLE", foreground=Colors.INFO)
        self.tree.tag_configure("ARCHIVE", foreground=Colors.MUTED)
        self.tree.tag_configure("DISPONIBLE", foreground=Colors.SUCCESS)
        self.tree.tag_configure("EN_UTILISATION", foreground=Colors.INFO)
        self.tree.tag_configure("SURVEILLANCE", foreground=Colors.WARNING)
        self.tree.tag_configure("MAINTENANCE", foreground=Colors.WARNING)
        self.tree.tag_configure("HORS_SERVICE", foreground=Colors.DANGER)
        self.tree.tag_configure("OUVERT", foreground=Colors.DANGER)
        self.tree.tag_configure("EN_COURS", foreground=Colors.WARNING)
        self.tree.tag_configure("RESOLU", foreground=Colors.SUCCESS)
        self.tree.tag_configure("CLOTURE", foreground=Colors.MUTED)
        self.tree.tag_configure("NOUVELLE", foreground=Colors.DANGER)
        self.tree.tag_configure("ACQUITTEE", foreground=Colors.INFO)
        self.tree.tag_configure("IGNOREE", foreground=Colors.MUTED)
        self.tree.tag_configure("RESOLUE", foreground=Colors.SUCCESS)
        self.tree.tag_configure("CRITIQUE", foreground=Colors.DANGER)
        self.tree.tag_configure("ALERTE", foreground=Colors.WARNING)
        self.tree.tag_configure("INFO", foreground=Colors.INFO)
        self.tree.tag_configure("warning", foreground=Colors.WARNING)
        self.tree.tag_configure("danger", foreground=Colors.DANGER)

    def clear(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def add(
        self,
        values: Iterable[object],
        *,
        item_id: Optional[str] = None,
        tags: Sequence[str] = (),
    ) -> str:
        options = {"values": tuple(values), "tags": tuple(tags)}
        if item_id is not None:
            return self.tree.insert("", "end", iid=item_id, **options)
        return self.tree.insert("", "end", **options)

    def selected_id(self) -> Optional[str]:
        selection = self.tree.selection()
        return selection[0] if selection else None
