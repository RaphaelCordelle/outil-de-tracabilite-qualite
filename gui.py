"""Fenêtre principale et navigation de l'application Tkinter."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from access import MODE_DESCRIPTIONS, MODE_LABELS, has_permission
from gui_theme import Colors, configure_theme
from gui_equipment import EquipmentView
from gui_views import (
    AnomaliesView,
    AuditView,
    ControlsView,
    DashboardView,
    LotsView,
    ReportsView,
    SettingsView,
)
from gui_widgets import Page
from quality_rules import ValidationError
from services import TraceabilityService
from storage import StorageError

USER_ERRORS = (StorageError, ValidationError, OSError, ValueError)


class QualityTraceabilityApp(tk.Tk):
    """Application de bureau utilisant le même service que la console."""

    NAVIGATION = (
        ("dashboard", "Tableau de bord", DashboardView),
        ("lots", "Lots", LotsView),
        ("controls", "Contrôles", ControlsView),
        ("equipment", "Équipements", EquipmentView),
        ("anomalies", "Anomalies", AnomaliesView),
        ("reports", "Rapports et exports", ReportsView),
        ("audit", "Journal d'audit", AuditView),
        ("settings", "Configuration", SettingsView),
    )
    MODE_NAVIGATION = {
        "EMPLOYE": {"dashboard", "lots", "controls", "equipment"},
        "QUALITE": {
            "dashboard",
            "lots",
            "controls",
            "equipment",
            "anomalies",
            "reports",
        },
        "MANAGER": {item[0] for item in NAVIGATION},
    }

    def __init__(self, service: TraceabilityService, root_path: Path) -> None:
        super().__init__()
        self.service = service
        self.root_path = Path(root_path)
        self.title("Quality Traceability Tool")
        self.geometry("1280x780")
        self.minsize(1060, 660)
        self.configure(background=Colors.BACKGROUND)
        configure_theme(self)
        self._center_on_screen()
        try:
            # L'application s'ouvre maximisée pour garder les tableaux lisibles
            # sur les écrans Windows avec mise à l'échelle 125 % ou 150 %.
            self.state("zoomed")
        except tk.TclError:
            # Certains gestionnaires de fenêtres Linux ne connaissent pas
            # l'état "zoomed" ; la géométrie 1280 × 780 reste alors utilisée.
            pass

        self.sidebar = tk.Frame(self, background=Colors.SIDEBAR, width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.main_area = ttk.Frame(self)
        self.main_area.pack(side="left", fill="both", expand=True)
        self.main_area.pack_propagate(False)

        role_bar = ttk.Frame(self.main_area, padding=(22, 10))
        role_bar.pack(side="top", fill="x")
        self.role_summary = tk.StringVar()
        ttk.Label(
            role_bar,
            textvariable=self.role_summary,
            style="Subtitle.TLabel",
        ).pack(side="left")
        self.role_value = tk.StringVar()
        self.role_selector = ttk.Combobox(
            role_bar,
            textvariable=self.role_value,
            values=tuple(MODE_LABELS.values()),
            state="readonly",
            width=22,
        )
        self.role_selector.pack(side="right")
        self.role_selector.bind("<<ComboboxSelected>>", self._change_role)
        ttk.Label(role_bar, text="Vue :").pack(side="right", padx=(0, 8))

        self.page_host = ttk.Frame(self.main_area)
        self.page_host.pack(fill="both", expand=True)
        self.page_host.pack_propagate(False)
        self.status_text = tk.StringVar(value="Prêt")
        tk.Label(
            self.main_area,
            textvariable=self.status_text,
            background="#E7EDF4",
            foreground=Colors.MUTED,
            anchor="w",
            padx=12,
            pady=5,
            font=("Segoe UI", 9),
        ).pack(fill="x", side="bottom")

        self.nav_buttons: dict[str, ttk.Button] = {}
        self.pages: dict[str, Page] = {}
        self.current_page = ""
        self._build_sidebar()
        self._build_pages()
        self.show_page("dashboard")
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    @property
    def mode(self) -> str:
        return self.service.rules.get("interface_mode", "QUALITE")

    def can(self, permission: str) -> bool:
        return has_permission(self.mode, permission)

    def _visible_navigation(self) -> tuple:
        visible = self.MODE_NAVIGATION.get(self.mode, self.MODE_NAVIGATION["QUALITE"])
        return tuple(item for item in self.NAVIGATION if item[0] in visible)

    def _center_on_screen(self) -> None:
        self.update_idletasks()
        width, height = 1280, 780
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build_sidebar(self) -> None:
        brand = tk.Frame(self.sidebar, background=Colors.SIDEBAR)
        brand.pack(fill="x", padx=18, pady=(20, 24))
        logo = tk.Label(
            brand,
            text="QT",
            background=Colors.PRIMARY,
            foreground="#FFFFFF",
            width=3,
            height=1,
            font=("Segoe UI Semibold", 16),
        )
        logo.pack(side="left")
        text = tk.Frame(brand, background=Colors.SIDEBAR)
        text.pack(side="left", padx=(10, 0))
        tk.Label(
            text,
            text="QUALITY",
            background=Colors.SIDEBAR,
            foreground="#FFFFFF",
            font=("Segoe UI Semibold", 11),
        ).pack(anchor="w")
        tk.Label(
            text,
            text="TRACEABILITY TOOL",
            background=Colors.SIDEBAR,
            foreground="#9EB0C7",
            font=("Segoe UI", 7),
        ).pack(anchor="w")

        self.navigation_frame = tk.Frame(self.sidebar, background=Colors.SIDEBAR)
        self.navigation_frame.pack(fill="x")
        self._build_navigation()

        footer = tk.Frame(self.sidebar, background=Colors.SIDEBAR)
        footer.pack(side="bottom", fill="x", padx=18, pady=18)
        self.role_text = tk.StringVar()
        self._update_role_label()
        tk.Label(
            footer,
            textvariable=self.role_text,
            background=Colors.SIDEBAR,
            foreground="#9EB0C7",
            font=("Segoe UI Semibold", 8),
        ).pack(anchor="w")
        tk.Label(
            footer,
            text="Prototype personnel",
            background=Colors.SIDEBAR,
            foreground="#72859E",
            justify="left",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(3, 0))
        tk.Button(
            footer,
            text="À propos",
            command=self._show_about,
            background=Colors.SIDEBAR,
            foreground="#9EB0C7",
            activebackground=Colors.SIDEBAR,
            activeforeground="#FFFFFF",
            borderwidth=0,
            cursor="hand2",
            font=("Segoe UI", 8, "underline"),
        ).pack(anchor="w", pady=(4, 0))

    def _build_navigation(self) -> None:
        for key, label, _view in self._visible_navigation():
            if key == "reports" and not self.can("export_data"):
                label = "Rapports"
            if key == "audit":
                label = "Historique"
            button = ttk.Button(
                self.navigation_frame,
                text=label,
                command=lambda page=key: self.show_page(page),
                style="Nav.TButton",
            )
            button.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = button

    def _show_about(self) -> None:
        messagebox.showinfo(
            "À propos",
            "Quality Traceability Tool\n\n"
            "Prototype personnel inspiré d'un environnement de production électronique.\n"
            "Les données, équipements et procédures présentés sont fictifs.",
            parent=self,
        )

    def _update_role_label(self) -> None:
        if hasattr(self, "role_text"):
            self.role_text.set(f"VUE : {MODE_LABELS.get(self.mode, self.mode).upper()}")
        if hasattr(self, "role_value"):
            self.role_value.set(MODE_LABELS.get(self.mode, self.mode))
            self.role_summary.set(MODE_DESCRIPTIONS.get(self.mode, ""))

    def _change_role(self, _event: tk.Event) -> None:
        selected = next(
            code for code, label in MODE_LABELS.items() if label == self.role_value.get()
        )
        if selected == self.mode:
            return
        try:
            self.service.update_interface_mode(selected)
        except USER_ERRORS as exc:
            self._update_role_label()
            messagebox.showerror("Changement impossible", str(exc), parent=self)
            return
        self.apply_interface_mode()

    def _build_pages(self) -> None:
        for key, _label, view_class in self._visible_navigation():
            self.pages[key] = view_class(self.page_host, self)

    def apply_interface_mode(self) -> None:
        if self.current_page and self.current_page in self.pages:
            self.pages[self.current_page].pack_forget()
        for page in self.pages.values():
            page.destroy()
        for button in self.nav_buttons.values():
            button.destroy()
        self.pages.clear()
        self.nav_buttons.clear()
        self.current_page = ""
        self._update_role_label()
        self._build_navigation()
        self._build_pages()
        self.show_page("dashboard")

    def show_page(self, key: str) -> None:
        if key not in self.pages:
            return
        if self.current_page:
            self.pages[self.current_page].pack_forget()
            self.nav_buttons[self.current_page].configure(style="Nav.TButton")
        self.current_page = key
        page = self.pages[key]
        page.pack(fill="both", expand=True)
        self.nav_buttons[key].configure(style="Active.Nav.TButton")
        page.refresh()
        self._update_status()

    def refresh_all(self) -> None:
        if self.current_page:
            self.pages[self.current_page].refresh()
        self._update_status()

    def reload_service(self) -> None:
        self.service = TraceabilityService(self.root_path)
        self.refresh_all()

    def _update_status(self) -> None:
        summary = self.service.summary()
        anomalies = len(self.service.active_tracked_anomalies())
        self.status_text.set(
            f"{MODE_LABELS.get(self.mode, self.mode)} • "
            f"{summary.total_lots} lot(s) • {summary.total_controles} contrôle(s) • "
            f"{len(self.service.open_equipment_issues())} incident(s) équipement • "
            f"{anomalies} alerte(s) • Taux pondéré "
            f"{summary.taux_defaut_moyen:.2f} %".replace(".", ",")
        )


def run_gui(service: TraceabilityService, root_path: Path) -> None:
    app = QualityTraceabilityApp(service, root_path)
    app.mainloop()
