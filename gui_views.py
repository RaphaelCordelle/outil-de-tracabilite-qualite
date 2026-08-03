"""Pages principales de l'application de bureau."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Optional
import webbrowser

from access import MODE_LABELS
from gui_dialogs import (
    ANOMALY_STATUS_LABELS,
    CONTROL_STATE_LABELS,
    AnomalyTrackingDialog,
    ControlDialog,
    LotDetailsDialog,
    LotDialog,
)
from gui_theme import Colors
from gui_widgets import DataTable, KpiCard, Page, Surface, display_code
from models import SuiviAnomalie
from quality_rules import ANOMALY_STATUS_TRANSITIONS, ValidationError
from reporting import generate_report
from storage import StorageError

USER_ERRORS = (StorageError, ValidationError, OSError, ValueError)


def _open_path(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            webbrowser.open(path.resolve().as_uri())
    except OSError as exc:
        messagebox.showerror("Ouverture impossible", str(exc))


AUDIT_LABELS = {
    "LOT_CREE": "Lot créé",
    "LOT_MODIFIE": "Lot modifié",
    "LOT_ARCHIVE": "Lot archivé",
    "LOT_REACTIVE": "Lot réactivé",
    "CONTROLE_AJOUTE": "Contrôle ajouté",
    "CONTROLE_MODIFIE": "Contrôle modifié",
    "ANOMALIE_MISE_A_JOUR": "Anomalie mise à jour",
    "INCIDENT_SIGNALE": "Incident signalé",
    "INCIDENT_MIS_A_JOUR": "Incident mis à jour",
    "UTILISATION_DEMARREE": "Utilisation démarrée",
    "UTILISATION_TERMINEE": "Utilisation terminée",
    "REGLES_MODIFIEES": "Configuration modifiée",
    "INCOHERENCES_CORRIGEES": "Calculs corrigés",
}


def _audit_label(code: str) -> str:
    return AUDIT_LABELS.get(code, code.replace("_", " ").capitalize())


# Tableau de bord, lots et contrôles

class DashboardView(Page):
    def __init__(self, parent: tk.Misc, app: Any) -> None:
        self.app = app
        descriptions = {
            "EMPLOYE": "Saisies du jour et état des équipements.",
            "QUALITE": "Contrôles, résultats et anomalies à traiter.",
            "MANAGER": "Vue générale de l'activité et des événements récents.",
        }
        super().__init__(
            parent,
            "Tableau de bord",
            descriptions.get(app.mode, "Activité du jour."),
            actions=(
                ("Nouveau lot", self._new_lot, "TButton"),
                ("Nouveau contrôle", self._new_control, "Primary.TButton"),
            ),
        )
        self.cards: dict[str, KpiCard] = {}
        cards = ttk.Frame(self.body)
        cards.pack(fill="x", pady=(0, 18))
        definitions = [
            ("lots", "Lots suivis", Colors.PRIMARY),
            ("conforme", "Lots conformes", Colors.SUCCESS),
            ("review", "À contrôler", Colors.WARNING),
            ("rejected", "Lots rejetés", Colors.DANGER),
        ]
        for column, (key, caption, color) in enumerate(definitions):
            card = KpiCard(cards, caption, "0", color)
            row, grid_column = divmod(column, 2)
            card.grid(
                row=row,
                column=grid_column,
                sticky="nsew",
                padx=(0, 8),
                pady=(0, 8),
            )
            cards.columnconfigure(
                grid_column, weight=1, uniform="dashboard_kpi"
            )
            self.cards[key] = card

        lower = ttk.Frame(self.body)
        lower.pack(fill="both", expand=True)

        anomalies = Surface(lower)
        anomalies.pack(fill="both", expand=True, pady=(0, 9))
        ttk.Label(anomalies, text="Alertes actuelles", style="Section.TLabel").pack(
            anchor="w", pady=(0, 10)
        )
        self.anomaly_table = DataTable(
            anomalies,
            [
                ("level", "Niveau", 90, "center"),
                ("description", "Description", 300, "w"),
            ],
            height=6,
            horizontal_scroll=False,
        )
        self.anomaly_table.pack(fill="both", expand=True)
        self.anomaly_table.tree.bind("<Double-1>", lambda _event: self._open_alert())
        ttk.Button(
            anomalies,
            text="Ouvrir l'élément sélectionné",
            command=self._open_alert,
        ).pack(anchor="e", pady=(8, 0))

        self.show_recent_events = app.can("view_audit")
        recent = Surface(lower)
        recent.pack(fill="x", pady=(9, 0))
        if self.show_recent_events:
            ttk.Label(recent, text="Événements récents", style="Section.TLabel").pack(
                anchor="w", pady=(0, 10)
            )
            self.audit_table = DataTable(
                recent,
                [
                    ("event", "Action", 200, "w"),
                    ("entity", "Élément", 180, "w"),
                ],
                height=3,
                horizontal_scroll=False,
            )
            self.audit_table.pack(fill="both", expand=True)
        else:
            guidance = {
                "EMPLOYE": (
                    "Vous pouvez créer un lot, saisir un contrôle en attente, "
                    "signaler un incident et enregistrer une utilisation."
                ),
                "QUALITE": (
                    "Vous pouvez valider les contrôles, traiter les anomalies "
                    "et générer le rapport qualité."
                ),
            }
            ttk.Label(recent, text="Actions disponibles", style="Section.TLabel").pack(
                anchor="w", pady=(0, 8)
            )
            ttk.Label(
                recent,
                text=guidance.get(app.mode, "Consultez le menu pour accéder aux actions."),
                style="Surface.TLabel",
                wraplength=850,
            ).pack(anchor="w")

    def _new_lot(self) -> None:
        LotDialog(self, self.app, self.app.refresh_all)

    def _new_control(self) -> None:
        ControlDialog(self, self.app, self.app.refresh_all)

    def _open_alert(self) -> None:
        selected = self.anomaly_table.selected_id()
        if not selected or ":" not in selected:
            messagebox.showinfo(
                "Sélection requise",
                "Sélectionnez une alerte dans le tableau.",
                parent=self,
            )
            return
        kind, item_id = selected.split(":", 1)
        page_key = "anomalies" if kind == "anomaly" else "equipment"
        if page_key not in self.app.pages:
            return
        self.app.show_page(page_key)
        page = self.app.pages[page_key]
        if kind == "anomaly":
            page.status_filter.set("TOUTES")
            page._refresh_table()
            table = page.table
        else:
            page.tabs.select(1)
            table = page.issue_table
        if table.tree.exists(item_id):
            table.tree.selection_set(item_id)
            table.tree.focus(item_id)
            table.tree.see(item_id)

    def refresh(self) -> None:
        summary = self.app.service.summary()
        self.cards["lots"].set_value(summary.total_lots)
        self.cards["conforme"].set_value(summary.lots_conformes)
        self.cards["review"].set_value(summary.lots_a_controler)
        self.cards["rejected"].set_value(summary.lots_rejetes)

        self.anomaly_table.clear()
        anomalies = (
            []
            if self.app.mode == "EMPLOYE"
            else self.app.service.active_tracked_anomalies()
        )
        equipment_issues = self.app.service.open_equipment_issues()
        if not anomalies and not equipment_issues:
            self.anomaly_table.add(("OK", "Aucune anomalie détectée"))
        for issue in equipment_issues[:6]:
            equipment = self.app.service.require_equipment(issue.id_equipement)
            self.anomaly_table.add(
                (
                    display_code(issue.gravite),
                    f"{equipment.nom} — {issue.description}",
                ),
                item_id=f"issue:{issue.id_incident}",
                tags=("danger" if issue.gravite == "CRITIQUE" else "warning",),
            )
        for anomaly in anomalies[:12]:
            level = anomaly.gravite
            tag = "warning" if level == "ALERTE" else "danger"
            self.anomaly_table.add(
                (display_code(level), anomaly.description),
                item_id=f"anomaly:{anomaly.id_anomalie}",
                tags=(tag,),
            )

        if self.show_recent_events:
            self.audit_table.clear()
            for event in reversed(self.app.service.repository.load_audit_events(limit=10)):
                self.audit_table.add(
                    (_audit_label(event["evenement"]), event["id_entite"])
                )


class LotsView(Page):
    def __init__(self, parent: tk.Misc, app: Any) -> None:
        self.app = app
        super().__init__(
            parent,
            "Lots de production",
            "Recherchez, consultez et gérez les lots de production.",
            actions=(("Créer un lot", self._new, "Primary.TButton"),),
        )
        filters = Surface(self.body, padding=12)
        filters.pack(fill="x", pady=(0, 12))
        ttk.Label(filters, text="Recherche", style="Surface.TLabel").pack(
            side="left", padx=(0, 8)
        )
        self.query = tk.StringVar()
        search = ttk.Entry(filters, textvariable=self.query, width=30)
        search.pack(side="left", padx=(0, 12))
        search.bind("<KeyRelease>", lambda _event: self.refresh())
        ttk.Label(filters, text="Statut", style="Surface.TLabel").pack(
            side="left", padx=(0, 8)
        )
        self.status = tk.StringVar(value="TOUS")
        status = ttk.Combobox(
            filters,
            textvariable=self.status,
            state="readonly",
            width=18,
            values=(
                "TOUS",
                "SANS_CONTROLE",
                "CONFORME",
                "A_CONTROLER",
                "REJETE",
                "ARCHIVE",
            ),
        )
        status.pack(side="left")
        status.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        self.count_label = ttk.Label(filters, style="Surface.TLabel")
        self.count_label.pack(side="right")

        container = Surface(self.body, padding=0)
        container.pack(fill="both", expand=True)
        self.table = DataTable(
            container,
            [
                ("id", "Identifiant", 180, "w"),
                ("date", "Création", 100, "center"),
                ("product", "Produit", 170, "w"),
                ("line", "Ligne", 90, "center"),
                ("quantity", "Quantité", 90, "e"),
                ("status", "Statut", 130, "center"),
                ("comment", "Commentaire", 260, "w"),
            ],
        )
        self.table.pack(fill="both", expand=True)
        self.table.tree.bind("<Double-1>", lambda _event: self._open())
        buttons = ttk.Frame(self.body)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Ouvrir la fiche", command=self._open).pack(side="left")
        ttk.Button(buttons, text="Modifier les informations", command=self._edit).pack(
            side="left", padx=8
        )
        ttk.Button(
            buttons,
            text="Saisir un contrôle",
            command=self._control,
            style="Primary.TButton",
        ).pack(side="left")

    def _selected(self) -> str:
        lot_id = self.table.selected_id()
        if not lot_id:
            messagebox.showinfo("Sélection requise", "Sélectionnez d'abord un lot.")
            return ""
        return lot_id

    def _new(self) -> None:
        LotDialog(self, self.app, self.app.refresh_all)

    def _open(self) -> None:
        lot_id = self._selected()
        if lot_id:
            LotDetailsDialog(self, self.app, lot_id, self.app.refresh_all)

    def _edit(self) -> None:
        lot_id = self._selected()
        if lot_id:
            LotDialog(
                self,
                self.app,
                self.app.refresh_all,
                self.app.service.require_lot(lot_id),
            )

    def _control(self) -> None:
        lot_id = self._selected()
        if lot_id:
            ControlDialog(self, self.app, self.app.refresh_all, lot_id)

    def refresh(self) -> None:
        query = self.query.get().strip().casefold()
        status = self.status.get()
        lots = self.app.service.lots
        if query:
            lots = self.app.service.search_lots(query)
        if status != "TOUS":
            lots = [lot for lot in lots if lot.statut == status]
        self.table.clear()
        for lot in lots:
            self.table.add(
                (
                    lot.id_lot,
                    lot.date_creation,
                    lot.produit,
                    lot.ligne_production,
                    lot.quantite_produite,
                    display_code(lot.statut),
                    lot.commentaire,
                ),
                item_id=lot.id_lot,
                tags=(lot.statut,),
            )
        self.count_label.configure(text=f"{len(lots)} lot(s)")


class ControlsView(Page):
    def __init__(self, parent: tk.Misc, app: Any) -> None:
        self.app = app
        super().__init__(
            parent,
            "Contrôles qualité",
            "Historique des contrôles et résultats calculés.",
            actions=(("Ajouter un contrôle", self._new, "Primary.TButton"),),
        )
        filters = Surface(self.body, padding=12)
        filters.pack(fill="x", pady=(0, 12))
        ttk.Label(filters, text="Recherche", style="Surface.TLabel").pack(
            side="left", padx=(0, 8)
        )
        self.query = tk.StringVar()
        search = ttk.Entry(filters, textvariable=self.query, width=34)
        search.pack(side="left")
        search.bind("<KeyRelease>", lambda _event: self.refresh())
        self.count_label = ttk.Label(filters, style="Surface.TLabel")
        self.count_label.pack(side="right")
        container = Surface(self.body, padding=0)
        container.pack(fill="both", expand=True)
        self.table = DataTable(
            container,
            [
                ("id", "Contrôle", 170, "w"),
                ("lot", "Lot", 170, "w"),
                ("date", "Date", 100, "center"),
                ("quantity", "Contrôlé", 90, "e"),
                ("defects", "Défauts", 80, "e"),
                ("rate", "Taux", 80, "e"),
                ("type", "Type de défaut", 160, "w"),
                ("result", "Résultat", 130, "center"),
                ("state", "État", 120, "center"),
                ("comment", "Commentaire", 220, "w"),
            ],
        )
        self.table.pack(fill="both", expand=True)
        self.table.tree.bind("<Double-1>", lambda _event: self._edit())
        actions = ttk.Frame(self.body)
        actions.pack(fill="x", pady=(10, 0))
        control_action = (
            "Modifier / changer l'état"
            if app.can("validate_controls")
            else "Modifier la saisie en attente"
        )
        ttk.Button(actions, text=control_action, command=self._edit).pack(side="left")
        ttk.Button(actions, text="Voir le lot", command=self._open_lot).pack(
            side="left", padx=8
        )

    def _new(self) -> None:
        ControlDialog(self, self.app, self.app.refresh_all)

    def _open_lot(self) -> None:
        selected = self.table.selected_id()
        if not selected:
            return
        control = next(
            item for item in self.app.service.controls if item.id_controle == selected
        )
        LotDetailsDialog(
            self, self.app, control.id_lot, self.app.refresh_all
        )

    def _edit(self) -> None:
        selected = self.table.selected_id()
        if not selected:
            messagebox.showwarning(
                "Sélection requise",
                "Sélectionnez un contrôle dans le tableau.",
                parent=self,
            )
            return
        control = self.app.service.require_control(selected)
        if not self.app.can("validate_controls") and control.etat_controle != "EN_ATTENTE":
            messagebox.showinfo(
                "Contrôle verrouillé",
                "Un contrôle validé ou annulé doit être modifié par le profil qualité.",
                parent=self,
            )
            return
        ControlDialog(
            self,
            self.app,
            self.app.refresh_all,
            control=control,
        )

    def refresh(self) -> None:
        query = self.query.get().strip().casefold()
        controls = [
            control
            for control in self.app.service.controls
            if not query
            or query in control.id_controle.casefold()
            or query in control.id_lot.casefold()
            or query in control.type_defaut.casefold()
            or query in control.resultat.casefold()
            or query in control.etat_controle.casefold()
        ]
        self.table.clear()
        for control in controls:
            self.table.add(
                (
                    control.id_controle,
                    control.id_lot,
                    control.date_controle,
                    control.quantite_controlee,
                    control.nombre_defauts,
                    f"{control.taux_defaut:.2f} %",
                    control.type_defaut,
                    display_code(control.resultat),
                    CONTROL_STATE_LABELS[control.etat_controle],
                    control.commentaire,
                ),
                item_id=control.id_controle,
                tags=(control.resultat,),
            )
        self.count_label.configure(text=f"{len(controls)} contrôle(s)")


# Suivi qualité et rapports

class AnomaliesView(Page):
    def __init__(self, parent: tk.Misc, app: Any) -> None:
        self.app = app
        super().__init__(
            parent,
            "Suivi des anomalies",
            "Anomalies repérées dans les lots et les contrôles.",
        )
        cards = ttk.Frame(self.body)
        cards.pack(fill="x", pady=(0, 12))
        self.cards = {
            "active": KpiCard(cards, "Anomalies actives", "0", Colors.DANGER),
            "new": KpiCard(cards, "Nouvelles", "0", Colors.WARNING),
            "progress": KpiCard(cards, "En cours", "0", Colors.INFO),
            "resolved": KpiCard(cards, "Résolues", "0", Colors.SUCCESS),
        }
        for column, card in enumerate(self.cards.values()):
            card.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(0, 8 if column < 3 else 0),
            )
            cards.columnconfigure(column, weight=1, uniform="anomaly_kpi")

        filters = Surface(self.body, padding=10)
        filters.pack(fill="x", pady=(0, 10))
        ttk.Label(filters, text="Recherche", style="Surface.TLabel").pack(
            side="left", padx=(0, 8)
        )
        self.query = tk.StringVar()
        search = ttk.Entry(filters, textvariable=self.query, width=30)
        search.pack(side="left")
        search.bind("<KeyRelease>", lambda _event: self._refresh_table())
        ttk.Label(filters, text="Afficher", style="Surface.TLabel").pack(
            side="left", padx=(18, 8)
        )
        self.status_filter = tk.StringVar(value="ACTIVES")
        status = ttk.Combobox(
            filters,
            textvariable=self.status_filter,
            values=(
                "ACTIVES",
                "TOUTES",
                "NOUVELLE",
                "ACQUITTEE",
                "EN_COURS",
                "IGNOREE",
                "RESOLUE",
            ),
            state="readonly",
            width=16,
        )
        status.pack(side="left")
        status.bind("<<ComboboxSelected>>", lambda _event: self._refresh_table())
        self.count_label = ttk.Label(filters, style="Surface.TLabel")
        self.count_label.pack(side="right")

        container = Surface(self.body, padding=0)
        container.pack(fill="both", expand=True)
        self.table = DataTable(
            container,
            [
                ("id", "Anomalie", 145, "w"),
                ("level", "Gravité", 90, "center"),
                ("entity", "Élément", 170, "w"),
                ("type", "Type", 180, "w"),
                ("description", "Description", 360, "w"),
                ("status", "Traitement", 115, "center"),
                ("updated", "Mise à jour", 145, "center"),
                ("comment", "Commentaire", 260, "w"),
            ],
            height=10,
        )
        self.table.pack(fill="both", expand=True)
        self.table.tree.bind("<Double-1>", lambda _event: self._edit())

        actions = ttk.Frame(self.body)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(
            actions,
            text="Traiter l'anomalie",
            command=self._edit,
            style="Primary.TButton",
        ).pack(side="left")
        ttk.Button(
            actions,
            text="Ignorer avec justification",
            command=self._ignore,
        ).pack(side="left", padx=7)

    def _selected(self) -> Optional[SuiviAnomalie]:
        anomaly_id = self.table.selected_id()
        if not anomaly_id:
            messagebox.showwarning(
                "Sélection requise",
                "Sélectionnez une anomalie dans le tableau.",
                parent=self,
            )
            return None
        return self.app.service.require_tracked_anomaly(anomaly_id)

    def _edit(self) -> None:
        anomaly = self._selected()
        if anomaly:
            AnomalyTrackingDialog(
                self, self.app, anomaly, self.app.refresh_all
            )

    def _ignore(self) -> None:
        anomaly = self._selected()
        if not anomaly:
            return
        if "IGNOREE" not in ANOMALY_STATUS_TRANSITIONS[anomaly.statut]:
            messagebox.showinfo(
                "Action indisponible",
                "Cette anomalie ne peut pas être ignorée dans son état actuel.",
                parent=self,
            )
            return
        reason = simpledialog.askstring(
            "Retirer de la vue active",
            (
                "Indiquez pourquoi cette anomalie peut être ignorée. "
                "Elle restera consultable dans l'historique :"
            ),
            parent=self,
            initialvalue=anomaly.commentaire,
        )
        if reason is None:
            return
        try:
            self.app.service.update_anomaly_tracking(
                anomaly.id_anomalie,
                statut="IGNOREE",
                commentaire=reason,
            )
        except USER_ERRORS as exc:
            messagebox.showerror("Retrait impossible", str(exc), parent=self)
            return
        self.app.refresh_all()

    def _refresh_table(self) -> None:
        anomalies = list(self.app.service.anomaly_tracking)
        selected_status = self.status_filter.get()
        if selected_status == "ACTIVES":
            anomalies = [
                item
                for item in anomalies
                if item.statut not in {"IGNOREE", "RESOLUE"}
            ]
        elif selected_status != "TOUTES":
            anomalies = [
                item for item in anomalies if item.statut == selected_status
            ]
        query = self.query.get().strip().casefold()
        if query:
            anomalies = [
                item
                for item in anomalies
                if query in item.id_anomalie.casefold()
                or query in item.entite_id.casefold()
                or query in item.type_anomalie.casefold()
                or query in item.description.casefold()
                or query in item.commentaire.casefold()
            ]
        anomalies.sort(key=lambda item: item.date_mise_a_jour, reverse=True)
        self.table.clear()
        for anomaly in anomalies:
            self.table.add(
                (
                    anomaly.id_anomalie,
                    display_code(anomaly.gravite),
                    f"{anomaly.entite_type} {anomaly.entite_id}",
                    display_code(anomaly.type_anomalie),
                    anomaly.description,
                    ANOMALY_STATUS_LABELS[anomaly.statut],
                    anomaly.date_mise_a_jour[:16].replace("T", " "),
                    anomaly.commentaire,
                ),
                item_id=anomaly.id_anomalie,
                tags=(anomaly.statut,),
            )
        self.count_label.configure(
            text=f"{len(anomalies)} anomalie(s) affichée(s)"
        )

    def refresh(self) -> None:
        tracking = self.app.service.synchronize_anomalies()
        statuses = Counter(item.statut for item in tracking)
        self.cards["active"].set_value(
            sum(
                item.statut not in {"IGNOREE", "RESOLUE"}
                for item in tracking
            )
        )
        self.cards["new"].set_value(statuses["NOUVELLE"])
        self.cards["progress"].set_value(statuses["EN_COURS"])
        self.cards["resolved"].set_value(statuses["RESOLUE"])
        self._refresh_table()


class ReportsView(Page):
    def __init__(self, parent: tk.Misc, app: Any) -> None:
        self.app = app
        super().__init__(
            parent,
            "Rapports" if not app.can("export_data") else "Rapports et exports",
            "Consultez une synthèse ou préparez une copie des données.",
        )

        help_box = Surface(self.body, padding=12)
        help_box.pack(fill="x", pady=(0, 12))
        help_text = (
            "Rapport : résumé lisible de la situation au moment de la génération."
        )
        if app.can("export_data"):
            help_text += (
                "  Export : copie complète des CSV et de la configuration, "
                "avec un fichier de contrôle d'intégrité."
            )
        ttk.Label(
            help_box,
            text=help_text,
            style="Surface.TLabel",
            wraplength=1050,
        ).pack(anchor="w")

        reports = Surface(self.body)
        reports.pack(fill="both", expand=True, pady=(0, 12))
        report_header = ttk.Frame(reports, style="Surface.TFrame")
        report_header.pack(fill="x", pady=(0, 4))
        ttk.Label(
            report_header, text="Rapports de suivi", style="Section.TLabel"
        ).pack(side="left")
        ttk.Button(
            report_header,
            text="Générer un rapport",
            command=self._report,
            style="Primary.TButton",
        ).pack(side="right")
        self.report_count = ttk.Label(report_header, style="Subtitle.TLabel")
        self.report_count.pack(side="right", padx=(0, 12))
        ttk.Label(
            reports,
            text="Sélectionnez un fichier puis ouvrez-le. Un double-clic fonctionne aussi.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(0, 10))
        ttk.Button(
            reports,
            text="Ouvrir le rapport sélectionné",
            command=self._open_report,
        ).pack(side="bottom", anchor="e", pady=(10, 0))
        self.report_table = DataTable(
            reports,
            [
                ("name", "Fichier", 430, "w"),
                ("type", "Type", 140, "center"),
                ("date", "Modifié le", 180, "center"),
                ("size", "Taille", 100, "e"),
            ],
            height=4,
        )
        self.report_table.pack(fill="both", expand=True)
        self.report_table.tree.bind("<Double-1>", lambda _event: self._open_report())

        self.export_table = None
        self.export_count = None
        if app.can("export_data"):
            exports = Surface(self.body)
            exports.pack(fill="both", expand=True)
            export_header = ttk.Frame(exports, style="Surface.TFrame")
            export_header.pack(fill="x", pady=(0, 4))
            ttk.Label(
                export_header, text="Copies des données", style="Section.TLabel"
            ).pack(side="left")
            ttk.Button(
                export_header,
                text="Créer un export",
                command=self._export,
            ).pack(side="right")
            self.export_count = ttk.Label(
                export_header, style="Subtitle.TLabel"
            )
            self.export_count.pack(side="right", padx=(0, 12))
            ttk.Label(
                exports,
                text="Sélectionnez un dossier pour consulter les fichiers exportés.",
                style="Subtitle.TLabel",
            ).pack(anchor="w", pady=(0, 10))
            ttk.Button(
                exports,
                text="Ouvrir l'export sélectionné",
                command=self._open_export,
            ).pack(side="bottom", anchor="e", pady=(10, 0))
            self.export_table = DataTable(
                exports,
                [
                    ("name", "Dossier", 500, "w"),
                    ("date", "Créé le", 180, "center"),
                    ("files", "Fichiers", 100, "e"),
                ],
                height=4,
            )
            self.export_table.pack(fill="both", expand=True)
            self.export_table.tree.bind(
                "<Double-1>", lambda _event: self._open_export()
            )

    def _report(self) -> None:
        try:
            path = generate_report(
                self.app.root_path,
                self.app.service.lots,
                self.app.service.controls,
                self.app.service.rules,
                self.app.service.equipment,
                self.app.service.equipment_issues,
                self.app.service.equipment_usage,
                self.app.service.tracked_anomalies(),
            )
        except USER_ERRORS as exc:
            messagebox.showerror("Rapport impossible", str(exc), parent=self)
            return
        self.refresh()
        self.report_table.tree.selection_set(path.name)
        self.report_table.tree.focus(path.name)
        self.report_table.tree.see(path.name)
        messagebox.showinfo(
            "Rapport prêt",
            "Le rapport a été ajouté à la liste.",
            parent=self,
        )

    def _export(self) -> None:
        try:
            path = self.app.service.repository.export(
                self.app.service.lots,
                self.app.service.controls,
                self.app.service.summary(),
                self.app.service.equipment,
                self.app.service.equipment_issues,
                self.app.service.equipment_usage,
                self.app.service.tracked_anomalies(),
            )
        except USER_ERRORS as exc:
            messagebox.showerror("Export impossible", str(exc), parent=self)
            return
        self.refresh()
        if self.export_table:
            self.export_table.tree.selection_set(path.name)
            self.export_table.tree.focus(path.name)
            self.export_table.tree.see(path.name)
        messagebox.showinfo(
            "Export prêt",
            "La copie des données a été ajoutée à la liste.",
            parent=self,
        )

    def _open_report(self) -> None:
        selected = self.report_table.selected_id()
        if not selected:
            messagebox.showwarning(
                "Sélection requise",
                "Sélectionnez un rapport dans la liste.",
                parent=self,
            )
            return
        _open_path(self.app.root_path / "reports" / selected)

    def _open_export(self) -> None:
        selected = self.export_table.selected_id() if self.export_table else None
        if not selected:
            messagebox.showwarning(
                "Sélection requise",
                "Sélectionnez un export dans la liste.",
                parent=self,
            )
            return
        _open_path(self.app.root_path / "exports" / selected)

    def refresh(self) -> None:
        self.report_table.clear()
        reports = sorted(
            (self.app.root_path / "reports").glob("*.md"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in reports:
            modified = path.stat().st_mtime
            self.report_table.add(
                (
                    path.name,
                    "Exemple livré"
                    if path.name == "example_quality_report.md"
                    else "Rapport généré",
                    datetime.fromtimestamp(modified).strftime("%d/%m/%Y %H:%M"),
                    f"{path.stat().st_size / 1024:.1f} Ko",
                ),
                item_id=path.name,
            )
        self.report_count.configure(text=f"{len(reports)} rapport(s)")
        if self.export_table is None:
            return
        self.export_table.clear()
        export_root = self.app.root_path / "exports"
        export_root.mkdir(parents=True, exist_ok=True)
        directories = sorted(
            (path for path in export_root.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in directories:
            self.export_table.add(
                (
                    path.name,
                    datetime.fromtimestamp(path.stat().st_mtime).strftime(
                        "%d/%m/%Y %H:%M"
                    ),
                    len(list(path.iterdir())),
                ),
                item_id=path.name,
            )
        if self.export_count:
            self.export_count.configure(text=f"{len(directories)} export(s)")


# Historique et configuration

class AuditView(Page):
    def __init__(self, parent: tk.Misc, app: Any) -> None:
        self.app = app
        super().__init__(
            parent,
            "Historique des actions",
            "Retrouvez les changements importants, leur date et le profil utilisé.",
        )
        filters = Surface(self.body, padding=10)
        filters.pack(fill="x", pady=(0, 10))
        ttk.Label(filters, text="Recherche", style="Surface.TLabel").pack(
            side="left", padx=(0, 8)
        )
        self.query = tk.StringVar()
        search = ttk.Entry(filters, textvariable=self.query, width=32)
        search.pack(side="left")
        search.bind("<KeyRelease>", lambda _event: self.refresh())
        ttk.Label(filters, text="Type", style="Surface.TLabel").pack(
            side="left", padx=(18, 8)
        )
        self.entity_filter = tk.StringVar(value="TOUS")
        entity = ttk.Combobox(
            filters,
            textvariable=self.entity_filter,
            values=(
                "TOUS",
                "LOT",
                "CONTROLE",
                "ANOMALIE",
                "EQUIPEMENT",
                "INCIDENT",
                "CONFIGURATION",
                "SYSTEME",
            ),
            state="readonly",
            width=16,
        )
        entity.pack(side="left")
        entity.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        container = Surface(self.body, padding=0)
        container.pack(fill="both", expand=True)
        self.table = DataTable(
            container,
            [
                ("timestamp", "Date", 150, "w"),
                ("profile", "Profil", 130, "center"),
                ("event", "Action", 190, "w"),
                ("entity", "Élément", 230, "w"),
                ("details", "Précision", 360, "w"),
            ],
        )
        self.table.pack(fill="both", expand=True)
        self.count = ttk.Label(self.body, style="Subtitle.TLabel")
        self.count.pack(anchor="w", pady=(10, 0))

    def refresh(self) -> None:
        events = list(reversed(self.app.service.repository.load_audit_events()))
        selected_type = self.entity_filter.get()
        if selected_type != "TOUS":
            events = [item for item in events if item["type_entite"] == selected_type]
        query = self.query.get().strip().casefold()
        if query:
            events = [
                item
                for item in events
                if query in item["evenement"].casefold()
                or query in item["id_entite"].casefold()
                or query in item["details"].casefold()
            ]
        self.table.clear()
        for event in events:
            timestamp = event["horodatage"][:16].replace("T", " ")
            profile = MODE_LABELS.get(event.get("profil", ""), "Système")
            self.table.add(
                (
                    timestamp,
                    profile,
                    _audit_label(event["evenement"]),
                    f"{event['type_entite']} — {event['id_entite']}",
                    event["details"],
                )
            )
        self.count.configure(
            text=(
                f"{len(events)} action(s) affichée(s). "
                "Le profil correspond au rôle sélectionné au moment de l'action."
            )
        )


class SettingsView(Page):
    def __init__(self, parent: tk.Misc, app: Any) -> None:
        self.app = app
        super().__init__(
            parent,
            "Configuration",
            "Seuils de contrôle, lignes de production et types de défaut.",
            actions=(
                ("Restaurer les données d'exemple", self._restore_demo, "TButton"),
                ("Enregistrer", self._save, "Primary.TButton"),
            ),
        )
        wrapper = ttk.Frame(self.body)
        wrapper.pack(fill="both", expand=True)
        wrapper.columnconfigure(0, weight=1)
        wrapper.columnconfigure(1, weight=1)

        thresholds = Surface(wrapper)
        thresholds.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        ttk.Label(thresholds, text="Seuils de décision", style="Section.TLabel").pack(
            anchor="w", pady=(0, 14)
        )
        self.conforme = tk.StringVar()
        self.review = tk.StringVar()
        self.abnormal = tk.StringVar()
        for label, variable in (
            ("Conforme jusqu'à (%)", self.conforme),
            ("À contrôler jusqu'à (%)", self.review),
            ("Alerte anormale au-delà de (%)", self.abnormal),
        ):
            row = ttk.Frame(thresholds, style="Surface.TFrame")
            row.pack(fill="x", pady=7)
            ttk.Label(row, text=label, style="Surface.TLabel").pack(side="left")
            ttk.Entry(row, textvariable=variable, width=12).pack(side="right")
        tk.Label(
            thresholds,
            text=(
                "La modification recalcule les résultats des contrôles et les statuts "
                "des lots. Une sauvegarde JSON .bak est conservée."
            ),
            background=Colors.INFO_BG,
            foreground=Colors.INFO,
            wraplength=430,
            justify="left",
            padx=12,
            pady=10,
        ).pack(fill="x", pady=(18, 0))

        refs = Surface(wrapper)
        refs.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        ttk.Label(refs, text="Référentiels actifs", style="Section.TLabel").pack(
            anchor="w", pady=(0, 14)
        )
        ttk.Label(refs, text="Lignes de production", style="KpiCaption.TLabel").pack(
            anchor="w"
        )
        self.lines = tk.Listbox(
            refs,
            height=5,
            borderwidth=1,
            relief="solid",
            font=("Segoe UI", 10),
        )
        self.lines.pack(fill="x", pady=(5, 8))
        line_actions = ttk.Frame(refs, style="Surface.TFrame")
        line_actions.pack(fill="x", pady=(0, 16))
        ttk.Button(
            line_actions,
            text="Ajouter",
            command=lambda: self._add_reference(self.lines, "Nouvelle ligne"),
        ).pack(side="left")
        ttk.Button(
            line_actions,
            text="Retirer",
            command=lambda: self._remove_reference(self.lines),
        ).pack(side="left", padx=6)
        ttk.Label(refs, text="Types de défaut", style="KpiCaption.TLabel").pack(
            anchor="w"
        )
        self.defects = tk.Listbox(
            refs,
            height=8,
            borderwidth=1,
            relief="solid",
            font=("Segoe UI", 10),
        )
        self.defects.pack(fill="x", pady=(5, 0))
        defect_actions = ttk.Frame(refs, style="Surface.TFrame")
        defect_actions.pack(fill="x", pady=(10, 0))
        ttk.Button(
            defect_actions,
            text="Ajouter",
            command=lambda: self._add_reference(
                self.defects, "Nouveau type de défaut"
            ),
        ).pack(side="left")
        ttk.Button(
            defect_actions,
            text="Retirer",
            command=lambda: self._remove_reference(self.defects),
        ).pack(side="left", padx=6)

    @staticmethod
    def _list_values(widget: tk.Listbox) -> list[str]:
        return list(widget.get(0, "end"))

    def _add_reference(self, widget: tk.Listbox, title: str) -> None:
        value = simpledialog.askstring(
            title,
            "Identifiant (majuscules, chiffres, _ ou -) :",
            parent=self,
        )
        if value is None:
            return
        normalized = value.strip().upper().replace(" ", "_")
        if not normalized:
            return
        if normalized in self._list_values(widget):
            messagebox.showwarning(
                "Valeur existante",
                f"{normalized} figure déjà dans le référentiel.",
                parent=self,
            )
            return
        widget.insert("end", normalized)
        widget.selection_clear(0, "end")
        widget.selection_set("end")

    def _remove_reference(self, widget: tk.Listbox) -> None:
        selection = widget.curselection()
        if not selection:
            messagebox.showwarning(
                "Sélection requise",
                "Sélectionnez une valeur à retirer.",
                parent=self,
            )
            return
        widget.delete(selection[0])

    def _save(self) -> None:
        try:
            rules = deepcopy(self.app.service.rules)
            rules["thresholds"] = {
                "conforme_max": float(self.conforme.get().replace(",", ".")),
                "a_controler_max": float(self.review.get().replace(",", ".")),
                "abnormal_rate": float(self.abnormal.get().replace(",", ".")),
            }
            rules["production_lines"] = self._list_values(self.lines)
            rules["defect_types"] = self._list_values(self.defects)
            corrections = self.app.service.update_rules(rules)
        except USER_ERRORS as exc:
            messagebox.showerror("Configuration invalide", str(exc), parent=self)
            return
        messagebox.showinfo(
            "Configuration enregistrée",
            f"Configuration enregistrée. {corrections} valeur(s) recalculée(s).",
            parent=self,
        )
        self.app.refresh_all()

    def _restore_demo(self) -> None:
        if not messagebox.askyesno(
            "Restaurer les données d'exemple",
            "Les données actuelles seront sauvegardées puis remplacées. Continuer ?",
            parent=self,
        ):
            return
        try:
            self.app.service.repository.restore_sample_data()
            self.app.reload_service()
        except USER_ERRORS as exc:
            messagebox.showerror("Restauration impossible", str(exc), parent=self)
            return
        messagebox.showinfo(
            "Données restaurées",
            "Le jeu de données d'exemple est à nouveau disponible.",
            parent=self,
        )

    def refresh(self) -> None:
        rules = self.app.service.rules
        self.conforme.set(str(rules["thresholds"]["conforme_max"]))
        self.review.set(str(rules["thresholds"]["a_controler_max"]))
        self.abnormal.set(str(rules["thresholds"]["abnormal_rate"]))
        self.lines.delete(0, "end")
        for line in rules["production_lines"]:
            self.lines.insert("end", line)
        self.defects.delete(0, "end")
        for defect in rules["defect_types"]:
            self.defects.insert("end", defect)
