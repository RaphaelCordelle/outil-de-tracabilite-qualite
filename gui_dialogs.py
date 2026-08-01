"""Formulaires et fenêtres de détail de l'interface graphique."""

from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Optional

from gui_theme import Colors, center_window
from gui_widgets import DataTable, StatusLabel


CONTROL_STATE_LABELS = {
    "EN_ATTENTE": "En attente",
    "VALIDE": "Validé",
    "ANNULE": "Annulé",
}
ANOMALY_STATUS_LABELS = {
    "NOUVELLE": "Nouvelle",
    "ACQUITTEE": "Acquittée",
    "EN_COURS": "En cours",
    "IGNOREE": "Ignorée",
    "RESOLUE": "Résolue",
}


def _field_label(parent: tk.Misc, text: str, row: int) -> None:
    ttk.Label(parent, text=text, style="Surface.TLabel").grid(
        row=row, column=0, sticky="w", padx=(0, 16), pady=7
    )


class FormDialog(tk.Toplevel):
    """Fenêtre modale avec zone d'erreur et boutons cohérents."""

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        width: int,
        height: int,
        on_success: Callable[[], None],
        submit_label: str = "Enregistrer",
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.configure(background=Colors.BACKGROUND)
        self.resizable(True, True)
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.on_success = on_success
        safe_height = min(height, max(480, self.winfo_screenheight() - 80))
        center_window(self, width, safe_height)
        self.minsize(min(width, 520), min(safe_height, 480))

        ttk.Label(self, text=title, style="Title.TLabel").pack(
            anchor="w", padx=24, pady=(20, 4)
        )
        buttons = ttk.Frame(self)
        buttons.pack(side="bottom", fill="x", padx=24, pady=(8, 20))
        ttk.Button(buttons, text="Annuler", command=self.destroy).pack(side="right")
        self.submit_button = ttk.Button(
            buttons,
            text=submit_label,
            command=self.submit,
            style="Primary.TButton",
        )
        self.submit_button.pack(side="right", padx=(0, 8))
        self.error = tk.StringVar()
        tk.Label(
            self,
            textvariable=self.error,
            foreground=Colors.DANGER,
            background=Colors.BACKGROUND,
            anchor="w",
        ).pack(side="bottom", fill="x", padx=24)
        self.form = ttk.Frame(self, style="Surface.TFrame", padding=20)
        self.form.pack(side="top", fill="both", expand=True, padx=24, pady=(10, 8))
        self.form.columnconfigure(1, weight=1)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Control-Return>", lambda _event: self.submit())

    def submit(self) -> None:
        raise NotImplementedError

    def _success(self) -> None:
        self.on_success()
        self.destroy()

    def _show_error(self, exc: Exception) -> None:
        self.error.set(str(exc))


class LotDialog(FormDialog):
    def __init__(
        self,
        parent: tk.Misc,
        app: Any,
        on_success: Callable[[], None],
        lot: Optional[Any] = None,
    ) -> None:
        self.app = app
        self.service = app.service
        self.lot = lot
        super().__init__(
            parent,
            "Modifier le lot" if lot else "Créer un lot",
            610,
            570,
            on_success,
        )
        default_id = lot.id_lot if lot else self.service.next_lot_id()
        self.id_var = tk.StringVar(value=default_id)
        self.date_var = tk.StringVar(
            value=lot.date_creation if lot else date.today().isoformat()
        )
        self.product_var = tk.StringVar(value=lot.produit if lot else "")
        self.quantity_var = tk.StringVar(
            value=str(lot.quantite_produite) if lot else ""
        )
        self.line_var = tk.StringVar(
            value=(
                lot.ligne_production
                if lot
                else self.service.rules["production_lines"][0]
            )
        )

        fields = [
            ("Identifiant", self.id_var),
            ("Date de création", self.date_var),
            ("Référence produit", self.product_var),
            ("Quantité produite", self.quantity_var),
        ]
        first_entry = None
        for row, (label, variable) in enumerate(fields):
            _field_label(self.form, label, row)
            entry = ttk.Entry(self.form, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew", pady=7)
            if first_entry is None:
                first_entry = entry
            if lot and row == 0:
                entry.configure(state="disabled")

        _field_label(self.form, "Ligne de production", 4)
        ttk.Combobox(
            self.form,
            textvariable=self.line_var,
            values=self.service.rules["production_lines"],
            state="readonly",
        ).grid(row=4, column=1, sticky="ew", pady=7)
        _field_label(self.form, "Commentaire", 5)
        self.comment = tk.Text(
            self.form,
            height=5,
            wrap="word",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 10),
        )
        self.comment.grid(row=5, column=1, sticky="ew", pady=7)
        if lot:
            self.comment.insert("1.0", lot.commentaire)
        if first_entry:
            first_entry.focus_set()

    def submit(self) -> None:
        try:
            quantity = int(self.quantity_var.get())
            comment = self.comment.get("1.0", "end").strip()
            if self.lot:
                self.service.update_lot(
                    self.lot.id_lot,
                    date_creation=self.date_var.get().strip(),
                    produit=self.product_var.get().strip().upper(),
                    quantite_produite=quantity,
                    ligne_production=self.line_var.get().strip().upper(),
                    commentaire=comment,
                )
            else:
                self.service.create_lot(
                    self.app.dependencies.lot_type(
                        id_lot=self.id_var.get().strip().upper(),
                        date_creation=self.date_var.get().strip(),
                        produit=self.product_var.get().strip().upper(),
                        quantite_produite=quantity,
                        ligne_production=self.line_var.get().strip().upper(),
                        commentaire=comment,
                    )
                )
        except self.app.dependencies.error_types as exc:
            self._show_error(exc)
            return
        self._success()


class ControlDialog(FormDialog):
    def __init__(
        self,
        parent: tk.Misc,
        app: Any,
        on_success: Callable[[], None],
        lot_id: str = "",
        control: Optional[Any] = None,
    ) -> None:
        self.app = app
        self.service = app.service
        self.control = control
        title = "Modifier le contrôle" if control else "Ajouter un contrôle qualité"
        super().__init__(parent, title, 630, 700, on_success)
        active_lots = [
            lot.id_lot for lot in self.service.lots if lot.statut != "ARCHIVE"
        ]
        self.id_var = tk.StringVar(
            value=(
                control.id_controle
                if control
                else self.service.next_control_id()
            )
        )
        self.lot_var = tk.StringVar(
            value=(
                control.id_lot
                if control
                else lot_id or (active_lots[0] if active_lots else "")
            )
        )
        self.date_var = tk.StringVar(
            value=control.date_controle if control else date.today().isoformat()
        )
        self.inspected_var = tk.StringVar(
            value=str(control.quantite_controlee) if control else ""
        )
        self.defects_var = tk.StringVar(
            value=str(control.nombre_defauts) if control else "0"
        )
        self.defect_type_var = tk.StringVar(
            value=(
                control.type_defaut
                if control
                else self.service.rules["defect_types"][0]
            )
        )
        self.state_var = tk.StringVar(
            value=CONTROL_STATE_LABELS[
                control.etat_controle
                if control
                else "VALIDE" if app.can("validate_controls") else "EN_ATTENTE"
            ]
        )

        _field_label(self.form, "Identifiant", 0)
        ttk.Entry(
            self.form,
            textvariable=self.id_var,
            state="disabled" if control else "normal",
        ).grid(
            row=0, column=1, sticky="ew", pady=7
        )
        _field_label(self.form, "Lot concerné", 1)
        ttk.Combobox(
            self.form,
            textvariable=self.lot_var,
            values=active_lots if not control else [control.id_lot],
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", pady=7)
        _field_label(self.form, "Date du contrôle", 2)
        ttk.Entry(self.form, textvariable=self.date_var).grid(
            row=2, column=1, sticky="ew", pady=7
        )
        _field_label(self.form, "Quantité contrôlée", 3)
        ttk.Entry(self.form, textvariable=self.inspected_var).grid(
            row=3, column=1, sticky="ew", pady=7
        )
        _field_label(self.form, "Nombre de défauts", 4)
        ttk.Entry(self.form, textvariable=self.defects_var).grid(
            row=4, column=1, sticky="ew", pady=7
        )
        _field_label(self.form, "Type de défaut", 5)
        ttk.Combobox(
            self.form,
            textvariable=self.defect_type_var,
            values=[*self.service.rules["defect_types"], "AUTRE"],
            state="readonly",
        ).grid(row=5, column=1, sticky="ew", pady=7)
        _field_label(self.form, "État du contrôle", 6)
        ttk.Combobox(
            self.form,
            textvariable=self.state_var,
            values=(
                tuple(CONTROL_STATE_LABELS.values())
                if app.can("validate_controls")
                else (CONTROL_STATE_LABELS["EN_ATTENTE"],)
            ),
            state="readonly",
        ).grid(row=6, column=1, sticky="ew", pady=7)
        _field_label(self.form, "Commentaire", 7)
        self.comment = tk.Text(
            self.form,
            height=5,
            wrap="word",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 10),
        )
        self.comment.grid(row=7, column=1, sticky="ew", pady=7)
        if control and control.commentaire:
            self.comment.insert("1.0", control.commentaire)

    def submit(self) -> None:
        try:
            values = {
                "date_controle": self.date_var.get().strip(),
                "quantite_controlee": int(self.inspected_var.get()),
                "nombre_defauts": int(self.defects_var.get()),
                "type_defaut": self.defect_type_var.get().strip().upper(),
                "etat_controle": next(
                    code
                    for code, label in CONTROL_STATE_LABELS.items()
                    if label == self.state_var.get()
                ),
                "commentaire": self.comment.get("1.0", "end").strip(),
            }
            if self.control:
                control = self.service.update_control(
                    self.control.id_controle, **values
                )
            else:
                control = self.app.dependencies.control_type(
                    id_controle=self.id_var.get().strip().upper(),
                    id_lot=self.lot_var.get().strip().upper(),
                    taux_defaut=0.0,
                    resultat="",
                    **values,
                )
                self.service.add_control(control)
        except self.app.dependencies.error_types as exc:
            self._show_error(exc)
            return
        messagebox.showinfo(
            "Contrôle enregistré",
            f"Taux de défaut : {control.taux_defaut:.2f} %\n"
            f"Résultat calculé : {control.resultat}\n"
            f"État : {control.etat_controle}",
            parent=self,
        )
        self._success()


class AnomalyTrackingDialog(FormDialog):
    def __init__(
        self,
        parent: tk.Misc,
        app: Any,
        anomaly: Any,
        on_success: Callable[[], None],
    ) -> None:
        self.app = app
        self.anomaly = anomaly
        super().__init__(
            parent,
            f"Traiter l'anomalie {anomaly.id_anomalie}",
            700,
            700,
            on_success,
            "Valider le traitement",
        )
        self.status_var = tk.StringVar(
            value=ANOMALY_STATUS_LABELS[anomaly.statut]
        )
        facts = [
            ("Identifiant", anomaly.id_anomalie),
            ("Élément concerné", f"{anomaly.entite_type} — {anomaly.entite_id}"),
            ("Gravité", anomaly.gravite),
            ("Type", anomaly.type_anomalie.replace("_", " ")),
        ]
        for row, (caption, value) in enumerate(facts):
            _field_label(self.form, caption, row)
            ttk.Label(
                self.form,
                text=value,
                style="Surface.TLabel",
                font=("Segoe UI Semibold", 10),
            ).grid(row=row, column=1, sticky="w", pady=7)

        _field_label(self.form, "Description détectée", 4)
        description = tk.Text(
            self.form,
            height=4,
            wrap="word",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 10),
        )
        description.grid(row=4, column=1, sticky="ew", pady=7)
        description.insert("1.0", anomaly.description)
        description.configure(state="disabled")

        _field_label(self.form, "État de traitement", 5)
        ttk.Combobox(
            self.form,
            textvariable=self.status_var,
            values=tuple(ANOMALY_STATUS_LABELS.values()),
            state="readonly",
        ).grid(row=5, column=1, sticky="ew", pady=7)

        _field_label(self.form, "Commentaire / justification", 6)
        self.comment = tk.Text(
            self.form,
            height=5,
            wrap="word",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 10),
        )
        self.comment.grid(row=6, column=1, sticky="ew", pady=7)
        self.comment.insert("1.0", anomaly.commentaire)

        tk.Label(
            self.form,
            text=(
                "Ignorée : la cause est acceptée avec une justification. "
                "Résolue : la cause doit d'abord avoir disparu."
            ),
            background=Colors.INFO_BG,
            foreground=Colors.INFO,
            wraplength=440,
            justify="left",
            padx=10,
            pady=8,
        ).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def submit(self) -> None:
        try:
            self.app.service.update_anomaly_tracking(
                self.anomaly.id_anomalie,
                statut=next(
                    code
                    for code, label in ANOMALY_STATUS_LABELS.items()
                    if label == self.status_var.get()
                ),
                commentaire=self.comment.get("1.0", "end").strip(),
            )
        except self.app.dependencies.error_types as exc:
            self._show_error(exc)
            return
        self._success()


class LotDetailsDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        app: Any,
        lot_id: str,
        on_change: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.app = app
        self.service = app.service
        self.lot_id = lot_id
        self.on_change = on_change
        self.title(f"Détail du lot {lot_id}")
        self.configure(background=Colors.BACKGROUND)
        self.transient(parent.winfo_toplevel())
        center_window(self, 950, 690)
        self.minsize(820, 580)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build()

    def _build(self) -> None:
        details = self.service.lot_details(self.lot_id)
        lot = details.lot
        header = ttk.Frame(self, padding=(24, 20))
        header.pack(fill="x")
        title = ttk.Frame(header)
        title.pack(side="left")
        ttk.Label(title, text=lot.id_lot, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title,
            text=f"{lot.produit} • {lot.ligne_production}",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 0))
        StatusLabel(header, lot.statut).pack(side="right")

        content = ttk.Frame(self, style="Surface.TFrame", padding=20)
        content.pack(fill="both", expand=True, padx=24, pady=(0, 14))
        facts = [
            ("Date de création", lot.date_creation),
            ("Quantité produite", lot.quantite_produite),
            ("Total contrôlé", details.total_controle),
            ("Total défauts", details.total_defauts),
            ("Taux pondéré", f"{details.taux_defaut_pondere:.2f} %"),
            ("Commentaire", lot.commentaire or "—"),
        ]
        info = ttk.Frame(content, style="Surface.TFrame")
        info.pack(fill="x", pady=(0, 16))
        for index, (label, value) in enumerate(facts):
            block = ttk.Frame(info, style="Surface.TFrame", padding=(0, 4))
            block.grid(row=index // 3, column=index % 3, sticky="ew", padx=(0, 20))
            ttk.Label(block, text=label, style="KpiCaption.TLabel").pack(anchor="w")
            ttk.Label(
                block,
                text=str(value),
                style="Surface.TLabel",
                font=("Segoe UI Semibold", 10),
            ).pack(anchor="w", pady=(2, 0))
            info.columnconfigure(index % 3, weight=1)

        ttk.Label(content, text="Contrôles associés", style="Section.TLabel").pack(
            anchor="w", pady=(4, 10)
        )
        table = DataTable(
            content,
            [
                ("id", "Contrôle", 170, "w"),
                ("date", "Date", 100, "center"),
                ("quantity", "Contrôlé", 90, "e"),
                ("defects", "Défauts", 80, "e"),
                ("rate", "Taux", 80, "e"),
                ("type", "Type", 150, "w"),
                ("result", "Résultat", 120, "center"),
                ("state", "État", 110, "center"),
            ],
            height=8,
        )
        table.pack(fill="both", expand=True)
        for control in details.controles:
            table.add(
                (
                    control.id_controle,
                    control.date_controle,
                    control.quantite_controlee,
                    control.nombre_defauts,
                    f"{control.taux_defaut:.2f} %",
                    control.type_defaut,
                    control.resultat,
                    CONTROL_STATE_LABELS[control.etat_controle],
                ),
                item_id=control.id_controle,
                tags=(control.resultat,),
            )
        table.tree.bind(
            "<Double-1>",
            lambda _event: self._edit_control(table.selected_id()),
        )

        buttons = ttk.Frame(self, padding=(24, 0, 24, 20))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Fermer", command=self.destroy).pack(side="right")
        if self.app.can("edit_pending_control") or self.app.can("validate_controls"):
            ttk.Button(
                buttons,
                text="Modifier le contrôle",
                command=lambda: self._edit_control(table.selected_id()),
            ).pack(side="left", padx=(0, 8))
        if self.app.can("edit_lot"):
            ttk.Button(
                buttons,
                text="Modifier le lot",
                command=lambda: LotDialog(self, self.app, self._changed, lot),
            ).pack(side="left")
        if self.app.can("add_control"):
            ttk.Button(
                buttons,
                text="Ajouter un contrôle",
                command=lambda: ControlDialog(
                    self, self.app, self._changed, lot_id=lot.id_lot
                ),
                style="Primary.TButton",
            ).pack(side="left", padx=8)
        if self.app.can("archive_lot"):
            archive_text = "Réactiver" if lot.statut == "ARCHIVE" else "Archiver"
            ttk.Button(
                buttons,
                text=archive_text,
                command=self._toggle_archive,
                style="Danger.TButton" if lot.statut != "ARCHIVE" else "TButton",
            ).pack(side="left")

    def _edit_control(self, control_id: str) -> None:
        if not control_id:
            messagebox.showwarning(
                "Sélection requise",
                "Sélectionnez un contrôle dans le tableau.",
                parent=self,
            )
            return
        control = self.service.require_control(control_id)
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
            self._changed,
            control=control,
        )

    def _toggle_archive(self) -> None:
        lot = self.service.require_lot(self.lot_id)
        action = "réactiver" if lot.statut == "ARCHIVE" else "archiver"
        if not messagebox.askyesno(
            "Confirmation",
            f"Voulez-vous {action} le lot {lot.id_lot} ?",
            parent=self,
        ):
            return
        try:
            if lot.statut == "ARCHIVE":
                self.service.restore_lot(lot.id_lot)
            else:
                self.service.archive_lot(lot.id_lot)
        except self.app.dependencies.error_types as exc:
            messagebox.showerror("Opération impossible", str(exc), parent=self)
            return
        self._changed()

    def _changed(self) -> None:
        self.on_change()
        for child in self.winfo_children():
            # Le formulaire modal qui déclenche ce rappel se ferme lui-même
            # juste après. Le détruire ici provoquerait une double fermeture.
            if not isinstance(child, tk.Toplevel):
                child.destroy()
        self._build()
