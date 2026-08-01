"""Gestion graphique du parc d'équipements, des incidents et utilisations."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Optional

from gui_dialogs import FormDialog
from gui_theme import Colors
from gui_widgets import DataTable, KpiCard, Page, Surface


GUIDE_OPTIONS = {
    "Aucun guide": "",
    "Équipement rotatif": "docs/equipment-guides/extraction-mandrin.md",
    "Coupeuse de bandes": "docs/equipment-guides/coupeuse-bandes.md",
    "Poste aspirant de brasage": "docs/equipment-guides/poste-aspirant-brasage.md",
    "Table aspirante papier": "docs/equipment-guides/table-aspirante-papier.md",
    "Transpalette manuel": "docs/equipment-guides/transpalette-manuel.md",
}
EQUIPMENT_STATUS_LABELS = {
    "DISPONIBLE": "Disponible",
    "EN_UTILISATION": "En utilisation",
    "SURVEILLANCE": "Sous surveillance",
    "MAINTENANCE": "En maintenance",
    "HORS_SERVICE": "Hors service",
}
ISSUE_STATUS_LABELS = {
    "OUVERT": "Ouvert",
    "EN_COURS": "En cours",
    "RESOLU": "Résolu",
    "CLOTURE": "Clôturé",
}


def _label(parent: tk.Misc, text: str, row: int) -> None:
    ttk.Label(parent, text=text, style="Surface.TLabel").grid(
        row=row, column=0, sticky="w", padx=(0, 16), pady=7
    )


def _display_datetime(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value.replace("T", " ")


class EquipmentDialog(FormDialog):
    def __init__(
        self,
        parent: tk.Misc,
        app: Any,
        on_success: Callable[[], None],
        equipment: Optional[Any] = None,
    ) -> None:
        self.app = app
        self.service = app.service
        self.equipment = equipment
        super().__init__(
            parent,
            "Modifier l'équipement" if equipment else "Ajouter un équipement",
            690,
            720,
            on_success,
        )
        self.id_var = tk.StringVar(
            value=(
                equipment.id_equipement
                if equipment
                else self.service.next_equipment_id()
            )
        )
        self.name_var = tk.StringVar(value=equipment.nom if equipment else "")
        self.category_var = tk.StringVar(
            value=equipment.categorie if equipment else "PROCESS"
        )
        self.zone_var = tk.StringVar(value=equipment.zone if equipment else "")
        self.criticality_var = tk.StringVar(
            value=equipment.criticite if equipment else "MOYENNE"
        )
        self.status_var = tk.StringVar(
            value=EQUIPMENT_STATUS_LABELS[
                equipment.statut if equipment else "DISPONIBLE"
            ]
        )
        current_guide = equipment.guide_fichier if equipment else ""
        self.guide_var = tk.StringVar(
            value=next(
                (
                    label
                    for label, path in GUIDE_OPTIONS.items()
                    if path == current_guide
                ),
                "Aucun guide",
            )
        )

        fields = [
            ("Identifiant", self.id_var),
            ("Nom", self.name_var),
            ("Catégorie", self.category_var),
            ("Zone", self.zone_var),
        ]
        for row, (caption, variable) in enumerate(fields):
            _label(self.form, caption, row)
            entry = ttk.Entry(self.form, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew", pady=7)
            if equipment and row == 0:
                entry.configure(state="disabled")

        _label(self.form, "Criticité", 4)
        ttk.Combobox(
            self.form,
            textvariable=self.criticality_var,
            values=("FAIBLE", "MOYENNE", "HAUTE", "CRITIQUE"),
            state="readonly",
        ).grid(row=4, column=1, sticky="ew", pady=7)
        _label(self.form, "Statut", 5)
        ttk.Combobox(
            self.form,
            textvariable=self.status_var,
            values=tuple(
                EQUIPMENT_STATUS_LABELS[code]
                for code in ("DISPONIBLE", "SURVEILLANCE", "MAINTENANCE", "HORS_SERVICE")
            ),
            state="readonly",
        ).grid(row=5, column=1, sticky="ew", pady=7)
        _label(self.form, "Guide associé", 6)
        ttk.Combobox(
            self.form,
            textvariable=self.guide_var,
            values=list(GUIDE_OPTIONS),
            state="readonly",
        ).grid(row=6, column=1, sticky="ew", pady=7)
        ttk.Label(
            self.form,
            text="Laisser vide si aucun guide utilisateur n'est nécessaire.",
            style="KpiCaption.TLabel",
        ).grid(row=7, column=1, sticky="w")

        _label(self.form, "Description", 8)
        self.description = tk.Text(
            self.form, height=4, wrap="word", relief="solid", borderwidth=1
        )
        self.description.grid(row=8, column=1, sticky="ew", pady=7)
        _label(self.form, "Commentaire", 9)
        self.comment = tk.Text(
            self.form, height=3, wrap="word", relief="solid", borderwidth=1
        )
        self.comment.grid(row=9, column=1, sticky="ew", pady=7)
        if equipment:
            self.description.insert("1.0", equipment.description)
            self.comment.insert("1.0", equipment.commentaire)

    def submit(self) -> None:
        values = {
            "nom": self.name_var.get().strip(),
            "categorie": self.category_var.get().strip().upper(),
            "zone": self.zone_var.get().strip(),
            "criticite": self.criticality_var.get().strip().upper(),
            "statut": next(
                code
                for code, label in EQUIPMENT_STATUS_LABELS.items()
                if label == self.status_var.get()
            ),
            "description": self.description.get("1.0", "end").strip(),
            "guide_fichier": GUIDE_OPTIONS[self.guide_var.get()],
            "commentaire": self.comment.get("1.0", "end").strip(),
        }
        try:
            if self.equipment:
                self.service.update_equipment(
                    self.equipment.id_equipement, **values
                )
            else:
                self.service.create_equipment(
                    self.app.dependencies.equipment_type(
                        id_equipement=self.id_var.get().strip().upper(),
                        **values,
                    )
                )
        except self.app.dependencies.error_types as exc:
            self._show_error(exc)
            return
        self._success()


class IssueDialog(FormDialog):
    def __init__(
        self,
        parent: tk.Misc,
        app: Any,
        on_success: Callable[[], None],
        equipment_id: str = "",
    ) -> None:
        self.app = app
        self.service = app.service
        super().__init__(parent, "Signaler un problème", 650, 570, on_success)
        equipment_ids = [item.id_equipement for item in self.service.equipment]
        self.equipment_var = tk.StringVar(
            value=equipment_id or (equipment_ids[0] if equipment_ids else "")
        )
        self.severity_var = tk.StringVar(value="MAJEURE")
        self.category_var = tk.StringVar(value="FONCTIONNEMENT")
        _label(self.form, "Équipement", 0)
        ttk.Combobox(
            self.form,
            textvariable=self.equipment_var,
            values=equipment_ids,
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", pady=7)
        _label(self.form, "Gravité", 1)
        ttk.Combobox(
            self.form,
            textvariable=self.severity_var,
            values=("MINEURE", "MAJEURE", "CRITIQUE"),
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", pady=7)
        _label(self.form, "Catégorie", 2)
        ttk.Combobox(
            self.form,
            textvariable=self.category_var,
            values=(
                "FONCTIONNEMENT",
                "SECURITE",
                "ASPIRATION",
                "REGLAGE",
                "BRUIT_VIBRATION",
                "ACCES",
                "AUTRE",
            ),
        ).grid(row=2, column=1, sticky="ew", pady=7)
        _label(self.form, "Description factuelle", 3)
        self.description = tk.Text(
            self.form, height=8, wrap="word", relief="solid", borderwidth=1
        )
        self.description.grid(row=3, column=1, sticky="ew", pady=7)
        tk.Label(
            self.form,
            text=(
                "Un incident critique place automatiquement l'équipement hors "
                "service. N'intervenez pas sur une zone dangereuse."
            ),
            background=Colors.DANGER_BG,
            foreground=Colors.DANGER,
            wraplength=390,
            justify="left",
            padx=10,
            pady=8,
        ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def submit(self) -> None:
        try:
            issue = self.app.dependencies.issue_type(
                id_incident=self.service.next_issue_id(),
                id_equipement=self.equipment_var.get().strip(),
                date_signalement=datetime.now()
                .astimezone()
                .isoformat(timespec="seconds"),
                gravite=self.severity_var.get().strip().upper(),
                categorie=self.category_var.get().strip().upper(),
                description=self.description.get("1.0", "end").strip(),
            )
            self.service.report_equipment_issue(issue)
        except self.app.dependencies.error_types as exc:
            self._show_error(exc)
            return
        self._success()


class IssueUpdateDialog(FormDialog):
    def __init__(
        self,
        parent: tk.Misc,
        app: Any,
        issue: Any,
        on_success: Callable[[], None],
    ) -> None:
        self.app = app
        self.issue = issue
        super().__init__(
            parent, f"Mettre à jour {issue.id_incident}", 640, 470, on_success
        )
        self.status_var = tk.StringVar(value=ISSUE_STATUS_LABELS[issue.statut])
        _label(self.form, "Statut", 0)
        ttk.Combobox(
            self.form,
            textvariable=self.status_var,
            values=tuple(ISSUE_STATUS_LABELS.values()),
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", pady=7)
        _label(self.form, "Action réalisée / suivi", 1)
        self.action = tk.Text(
            self.form, height=8, wrap="word", relief="solid", borderwidth=1
        )
        self.action.grid(row=1, column=1, sticky="ew", pady=7)
        self.action.insert("1.0", issue.action)

    def submit(self) -> None:
        try:
            self.app.service.update_equipment_issue(
                self.issue.id_incident,
                statut=next(
                    code
                    for code, label in ISSUE_STATUS_LABELS.items()
                    if label == self.status_var.get()
                ),
                action=self.action.get("1.0", "end").strip(),
            )
        except self.app.dependencies.error_types as exc:
            self._show_error(exc)
            return
        self._success()


class UsageDialog(FormDialog):
    def __init__(
        self,
        parent: tk.Misc,
        app: Any,
        equipment_id: str,
        on_success: Callable[[], None],
    ) -> None:
        self.app = app
        self.equipment_id = equipment_id
        super().__init__(parent, "Démarrer une utilisation", 620, 440, on_success)
        self.user_var = tk.StringVar()
        _label(self.form, "Équipement", 0)
        ttk.Label(
            self.form,
            text=f"{equipment_id} — {app.service.require_equipment(equipment_id).nom}",
            style="Surface.TLabel",
        ).grid(row=0, column=1, sticky="w", pady=7)
        _label(self.form, "Utilisateur / initiales", 1)
        ttk.Entry(self.form, textvariable=self.user_var).grid(
            row=1, column=1, sticky="ew", pady=7
        )
        _label(self.form, "Motif ou opération", 2)
        self.reason = tk.Text(
            self.form, height=5, wrap="word", relief="solid", borderwidth=1
        )
        self.reason.grid(row=2, column=1, sticky="ew", pady=7)

    def submit(self) -> None:
        try:
            self.app.service.start_equipment_usage(
                self.equipment_id,
                self.user_var.get().strip(),
                self.reason.get("1.0", "end").strip(),
            )
        except self.app.dependencies.error_types as exc:
            self._show_error(exc)
            return
        self._success()


class EquipmentView(Page):
    def __init__(self, parent: tk.Misc, app: Any) -> None:
        self.app = app
        page_actions = []
        if app.can("manage_equipment"):
            page_actions.append(("Ajouter un équipement", self._new_equipment, "TButton"))
        if app.can("report_issue"):
            page_actions.append(("Signaler un problème", self._new_issue, "Primary.TButton"))
        super().__init__(
            parent,
            "Équipements",
            "Disponibilité, incidents, guides et temps d'utilisation du parc.",
            actions=tuple(page_actions),
        )
        cards = ttk.Frame(self.body)
        cards.pack(fill="x", pady=(0, 14))
        self.cards = {
            "total": KpiCard(cards, "Équipements suivis", "0", Colors.PRIMARY),
            "available": KpiCard(cards, "Disponibles", "0", Colors.SUCCESS),
            "issues": KpiCard(cards, "Incidents ouverts", "0", Colors.DANGER),
            "active": KpiCard(cards, "En utilisation", "0", Colors.INFO),
        }
        for column, card in enumerate(self.cards.values()):
            card.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(0, 8 if column < 3 else 0),
            )
            cards.columnconfigure(column, weight=1, uniform="equipment_kpi")

        self.tabs = ttk.Notebook(self.body)
        self.tabs.pack(fill="both", expand=True)
        self._build_fleet_tab()
        self._build_issue_tab()
        self._build_usage_tab()

    def _build_fleet_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Parc machines")
        filters = Surface(tab, padding=10)
        filters.pack(fill="x", pady=(0, 10))
        ttk.Label(filters, text="Recherche", style="Surface.TLabel").pack(
            side="left", padx=(0, 8)
        )
        self.query = tk.StringVar()
        entry = ttk.Entry(filters, textvariable=self.query, width=30)
        entry.pack(side="left")
        entry.bind("<KeyRelease>", lambda _event: self._refresh_fleet())
        ttk.Label(filters, text="Statut", style="Surface.TLabel").pack(
            side="left", padx=(18, 8)
        )
        self.status_filter = tk.StringVar(value="TOUS")
        status = ttk.Combobox(
            filters,
            textvariable=self.status_filter,
            values=(
                "TOUS",
                "DISPONIBLE",
                "EN_UTILISATION",
                "SURVEILLANCE",
                "MAINTENANCE",
                "HORS_SERVICE",
            ),
            state="readonly",
            width=18,
        )
        status.pack(side="left")
        status.bind("<<ComboboxSelected>>", lambda _event: self._refresh_fleet())

        self.fleet_table = DataTable(
            tab,
            [
                ("id", "Identifiant", 130, "w"),
                ("name", "Équipement", 240, "w"),
                ("category", "Catégorie", 115, "center"),
                ("zone", "Zone", 170, "w"),
                ("criticality", "Criticité", 100, "center"),
                ("status", "Statut", 130, "center"),
                ("guide", "Guide", 70, "center"),
            ],
            height=10,
        )
        self.fleet_table.pack(fill="both", expand=True)
        self.fleet_table.tree.bind(
            "<<TreeviewSelect>>", lambda _event: self._show_selection()
        )
        if self.app.can("manage_equipment"):
            self.fleet_table.tree.bind(
                "<Double-1>", lambda _event: self._edit_equipment()
            )

        detail = Surface(tab, padding=10)
        detail.pack(fill="x", pady=(10, 0))
        self.detail_var = tk.StringVar(value="Sélectionnez un équipement.")
        ttk.Label(
            detail,
            textvariable=self.detail_var,
            style="Surface.TLabel",
            wraplength=980,
        ).pack(anchor="w")
        actions = ttk.Frame(detail, style="Surface.TFrame")
        actions.pack(fill="x", pady=(8, 0))
        available_actions = []
        if self.app.can("manage_equipment"):
            available_actions.append(("Modifier", self._edit_equipment, "TButton"))
        if self.app.can("use_equipment"):
            available_actions.extend(
                [
                    ("Démarrer l'utilisation", self._start_usage, "Primary.TButton"),
                    ("Terminer l'utilisation", self._end_usage, "TButton"),
                ]
            )
        available_actions.append(("Consulter le guide", self._open_guide, "TButton"))
        if self.app.can("report_issue"):
            available_actions.append(
                ("Signaler un problème", self._new_issue, "Danger.TButton")
            )
        for caption, command, style in available_actions:
            ttk.Button(
                actions, text=caption, command=command, style=style
            ).pack(side="left", padx=(0, 7))

    def _build_issue_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Incidents")
        self.issue_table = DataTable(
            tab,
            [
                ("id", "Incident", 150, "w"),
                ("equipment", "Équipement", 140, "w"),
                ("date", "Signalé le", 180, "w"),
                ("severity", "Gravité", 100, "center"),
                ("category", "Catégorie", 130, "center"),
                ("status", "Statut", 110, "center"),
                ("description", "Description", 360, "w"),
                ("action", "Action / suivi", 320, "w"),
            ],
        )
        self.issue_table.pack(fill="both", expand=True)
        if self.app.can("manage_incidents"):
            self.issue_table.tree.bind(
                "<Double-1>", lambda _event: self._update_issue()
            )
        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(10, 0))
        if self.app.can("manage_incidents"):
            ttk.Button(
                actions,
                text="Changer l'état de l'incident",
                command=self._update_issue,
                style="Primary.TButton",
            ).pack(side="left")
        if self.app.can("report_issue"):
            ttk.Button(
                actions, text="Nouveau signalement", command=self._new_issue
            ).pack(side="left", padx=8)

    def _build_usage_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Historique d'utilisation")
        self.usage_table = DataTable(
            tab,
            [
                ("id", "Session", 155, "w"),
                ("equipment", "Équipement", 140, "w"),
                ("start", "Début", 185, "w"),
                ("end", "Fin", 185, "w"),
                ("user", "Utilisateur", 110, "center"),
                ("duration", "Durée", 90, "e"),
                ("reason", "Motif", 340, "w"),
            ],
        )
        self.usage_table.pack(fill="both", expand=True)
        ttk.Label(
            tab,
            text=(
                "Chaque démarrage et arrêt est horodaté et ajouté au journal "
                "d'audit local."
            ),
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(10, 0))

    def _selected_equipment_id(self, *, warn: bool = True) -> str:
        selected = self.fleet_table.selected_id()
        if not selected and warn:
            messagebox.showwarning(
                "Sélection requise",
                "Sélectionnez un équipement dans le parc.",
                parent=self,
            )
        return selected or ""

    def _new_equipment(self) -> None:
        if not self.app.can("manage_equipment"):
            return
        EquipmentDialog(self, self.app, self.app.refresh_all)

    def _edit_equipment(self) -> None:
        if not self.app.can("manage_equipment"):
            return
        equipment_id = self._selected_equipment_id()
        if equipment_id:
            EquipmentDialog(
                self,
                self.app,
                self.app.refresh_all,
                self.app.service.require_equipment(equipment_id),
            )

    def _new_issue(self) -> None:
        IssueDialog(
            self,
            self.app,
            self.app.refresh_all,
            self._selected_equipment_id(warn=False),
        )

    def _update_issue(self) -> None:
        if not self.app.can("manage_incidents"):
            return
        issue_id = self.issue_table.selected_id()
        if not issue_id:
            messagebox.showwarning(
                "Sélection requise",
                "Sélectionnez un incident dans le tableau.",
                parent=self,
            )
            return
        issue = self.app.service.require_equipment_issue(issue_id)
        IssueUpdateDialog(self, self.app, issue, self.app.refresh_all)

    def _start_usage(self) -> None:
        equipment_id = self._selected_equipment_id()
        if equipment_id:
            UsageDialog(
                self, self.app, equipment_id, self.app.refresh_all
            )

    def _end_usage(self) -> None:
        equipment_id = self._selected_equipment_id()
        if not equipment_id:
            return
        if not messagebox.askyesno(
            "Terminer l'utilisation",
            f"Enregistrer l'heure de fin pour {equipment_id} ?",
            parent=self,
        ):
            return
        try:
            usage = self.app.service.end_equipment_usage(equipment_id)
        except self.app.dependencies.error_types as exc:
            messagebox.showerror("Opération impossible", str(exc), parent=self)
            return
        messagebox.showinfo(
            "Utilisation terminée",
            f"Durée enregistrée : {usage.duree_minutes} minute(s).",
            parent=self,
        )
        self.app.refresh_all()

    def _open_guide(self) -> None:
        equipment_id = self._selected_equipment_id()
        if not equipment_id:
            return
        try:
            path = self.app.service.equipment_guide_path(equipment_id)
            if path is None:
                messagebox.showinfo(
                    "Aucun guide associé",
                    (
                        "Cet équipement ne nécessite pas de guide utilisateur "
                        "dans l'application. Utilisez le signalement en cas de problème."
                    ),
                    parent=self,
                )
                return
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                import webbrowser

                webbrowser.open(path.as_uri())
        except self.app.dependencies.error_types as exc:
            messagebox.showerror("Guide indisponible", str(exc), parent=self)

    def _show_selection(self) -> None:
        equipment_id = self._selected_equipment_id(warn=False)
        if not equipment_id:
            self.detail_var.set("Sélectionnez un équipement.")
            return
        item = self.app.service.require_equipment(equipment_id)
        open_count = sum(
            issue.statut in {"OUVERT", "EN_COURS"}
            for issue in self.app.service.equipment_issues_for(equipment_id)
        )
        active = self.app.service.active_equipment_usage(equipment_id)
        details = (
            f"{item.description}  •  {open_count} incident(s) ouvert(s)"
            f"  •  Guide : {'disponible' if item.guide_fichier else 'non requis'}"
        )
        if active:
            details += (
                f"  •  Utilisé par {active.utilisateur} depuis "
                f"{_display_datetime(active.debut)}"
            )
        self.detail_var.set(details)

    def _refresh_fleet(self) -> None:
        query = self.query.get().strip().casefold()
        status = self.status_filter.get()
        items = [
            item
            for item in self.app.service.equipment
            if (status == "TOUS" or item.statut == status)
            and (
                not query
                or query in item.id_equipement.casefold()
                or query in item.nom.casefold()
                or query in item.categorie.casefold()
                or query in item.zone.casefold()
            )
        ]
        self.fleet_table.clear()
        for item in items:
            self.fleet_table.add(
                (
                    item.id_equipement,
                    item.nom,
                    item.categorie,
                    item.zone,
                    item.criticite,
                    EQUIPMENT_STATUS_LABELS[item.statut],
                    "OUI" if item.guide_fichier else "—",
                ),
                item_id=item.id_equipement,
                tags=(item.statut,),
            )
        self._show_selection()

    def refresh(self) -> None:
        statuses = Counter(item.statut for item in self.app.service.equipment)
        self.cards["total"].set_value(len(self.app.service.equipment))
        self.cards["available"].set_value(statuses["DISPONIBLE"])
        self.cards["issues"].set_value(
            len(self.app.service.open_equipment_issues())
        )
        self.cards["active"].set_value(statuses["EN_UTILISATION"])
        self._refresh_fleet()

        self.issue_table.clear()
        for issue in sorted(
            self.app.service.equipment_issues,
            key=lambda item: item.date_signalement,
            reverse=True,
        ):
            self.issue_table.add(
                (
                    issue.id_incident,
                    issue.id_equipement,
                    _display_datetime(issue.date_signalement),
                    issue.gravite,
                    issue.categorie,
                    ISSUE_STATUS_LABELS[issue.statut],
                    issue.description,
                    issue.action,
                ),
                item_id=issue.id_incident,
                tags=(issue.statut,),
            )

        self.usage_table.clear()
        for usage in sorted(
            self.app.service.equipment_usage,
            key=lambda item: item.debut,
            reverse=True,
        ):
            self.usage_table.add(
                (
                    usage.id_utilisation,
                    usage.id_equipement,
                    _display_datetime(usage.debut),
                    _display_datetime(usage.fin) if usage.fin else "EN COURS",
                    usage.utilisateur,
                    f"{usage.duree_minutes} min" if usage.fin else "—",
                    usage.motif,
                ),
                item_id=usage.id_utilisation,
                tags=("warning",) if not usage.fin else (),
            )
