"""Orchestration des cas d'usage du MVP.

Cette couche rassemble les règles de transaction : validation avant écriture,
mise à jour des index, consolidation des statuts et journalisation métier.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date
import logging
from pathlib import Path

from models import ControleQualite, Lot, LotDetails, QualitySummary
from quality_rules import (
    calculate_defect_rate,
    consolidate_status,
    determine_result,
    weighted_defect_rate,
)
from storage import CsvRepository, StorageError
from validation import (
    ValidationError,
    detect_anomalies,
    validate_control,
    validate_lot,
    validate_rules,
)

LOGGER = logging.getLogger(__name__)


class TraceabilityService:
    """Façade métier utilisée par la console, les tests et les rapports."""

    def __init__(self, root: Path) -> None:
        self.repository = CsvRepository(root)
        self.rules = self.repository.load_rules()
        validate_rules(self.rules)
        self.lots = self.repository.load_lots()
        self.controls = self.repository.load_controls()
        self._rebuild_indexes()
        self._validate_loaded_data()

    def _rebuild_indexes(self) -> None:
        self._lots_by_id = {lot.id_lot: lot for lot in self.lots}
        self._controls_by_id = {
            control.id_controle: control for control in self.controls
        }
        self._controls_by_lot: dict[str, list[ControleQualite]] = defaultdict(list)
        for control in self.controls:
            self._controls_by_lot[control.id_lot].append(control)
        if len(self._lots_by_id) != len(self.lots):
            raise ValidationError("Le fichier lots.csv contient un identifiant dupliqué.")
        if len(self._controls_by_id) != len(self.controls):
            raise ValidationError(
                "Le fichier controls.csv contient un identifiant dupliqué."
            )

    def _validate_loaded_data(self) -> None:
        for lot in self.lots:
            validate_lot(lot, self.rules)
        for control in self.controls:
            lot = self._lots_by_id.get(control.id_lot)
            if lot is not None:
                validate_control(control, lot, self.rules)

    def _audit(
        self, event: str, entity_type: str, entity_id: str, details: str = ""
    ) -> None:
        try:
            self.repository.record_event(event, entity_type, entity_id, details)
        except StorageError as exc:
            # Une indisponibilité du journal ne doit pas annuler une donnée déjà
            # sauvegardée. Elle reste visible dans le log technique.
            LOGGER.warning("Événement d'audit non enregistré : %s", exc)

    def create_lot(self, lot: Lot) -> Lot:
        if self.get_lot(lot.id_lot):
            raise ValidationError(f"Le lot {lot.id_lot} existe déjà.")
        lot.statut = "SANS_CONTROLE"
        validate_lot(lot, self.rules)
        self.lots.append(lot)
        self._lots_by_id[lot.id_lot] = lot
        try:
            self.repository.save_lots(self.lots)
        except Exception:
            self.lots.remove(lot)
            self._lots_by_id.pop(lot.id_lot, None)
            raise
        self._audit("LOT_CREE", "LOT", lot.id_lot, f"Produit {lot.produit}")
        return lot

    def update_lot(self, lot_id: str, **changes: object) -> Lot:
        """Met à jour un lot sans rendre ses contrôles historiques invalides."""

        lot = self.require_lot(lot_id)
        original = replace(lot)
        protected = {"id_lot", "statut"}
        allowed = {
            "date_creation",
            "produit",
            "quantite_produite",
            "ligne_production",
            "commentaire",
        }
        unknown = set(changes) - allowed - protected
        if unknown:
            raise ValidationError(
                f"Champ de modification inconnu : {', '.join(sorted(unknown))}."
            )
        try:
            for field, value in changes.items():
                if field not in protected and value is not None:
                    setattr(lot, field, value)
            validate_lot(lot, self.rules)
            for control in self.controls_for_lot(lot_id):
                validate_control(control, lot, self.rules)
            self._refresh_status(lot.id_lot)
            self.repository.save_lots(self.lots)
        except Exception:
            for field, value in original.to_dict().items():
                setattr(lot, field, value)
            raise
        changed = [
            field
            for field, value in lot.to_dict().items()
            if value != original.to_dict()[field]
        ]
        self._audit(
            "LOT_MODIFIE",
            "LOT",
            lot.id_lot,
            f"Champs : {', '.join(changed) if changed else 'aucun'}",
        )
        return lot

    def archive_lot(self, lot_id: str) -> Lot:
        lot = self.require_lot(lot_id)
        if lot.statut == "ARCHIVE":
            raise ValidationError(f"Le lot {lot_id} est déjà archivé.")
        previous = lot.statut
        lot.statut = "ARCHIVE"
        try:
            self.repository.save_lots(self.lots)
        except Exception:
            lot.statut = previous
            raise
        self._audit("LOT_ARCHIVE", "LOT", lot.id_lot)
        return lot

    def restore_lot(self, lot_id: str) -> Lot:
        lot = self.require_lot(lot_id)
        if lot.statut != "ARCHIVE":
            raise ValidationError(f"Le lot {lot_id} n'est pas archivé.")
        lot.statut = consolidate_status(
            control.resultat for control in self.controls_for_lot(lot_id)
        )
        try:
            self.repository.save_lots(self.lots)
        except Exception:
            lot.statut = "ARCHIVE"
            raise
        self._audit("LOT_REACTIVE", "LOT", lot.id_lot, f"Statut {lot.statut}")
        return lot

    def get_lot(self, lot_id: str) -> Lot | None:
        return self._lots_by_id.get(lot_id)

    def require_lot(self, lot_id: str) -> Lot:
        lot = self.get_lot(lot_id)
        if lot is None:
            raise ValidationError(f"Lot {lot_id} introuvable.")
        return lot

    def search_lots(self, query: str = "", field: str = "all") -> list[Lot]:
        query = query.strip().casefold()
        allowed = {
            "id": "id_lot",
            "produit": "produit",
            "ligne": "ligne_production",
            "statut": "statut",
        }
        if field not in {*allowed, "all"}:
            raise ValidationError(f"Filtre de recherche inconnu : {field}.")
        if field in allowed:
            return [
                lot
                for lot in self.lots
                if query in str(getattr(lot, allowed[field])).casefold()
            ]
        return [
            lot
            for lot in self.lots
            if any(query in str(value).casefold() for value in lot.to_dict().values())
        ]

    def controls_for_lot(self, lot_id: str) -> list[ControleQualite]:
        self.require_lot(lot_id)
        return list(self._controls_by_lot.get(lot_id, []))

    def lot_details(self, lot_id: str) -> LotDetails:
        lot = self.require_lot(lot_id)
        controls = tuple(self.controls_for_lot(lot_id))
        inspected = sum(control.quantite_controlee for control in controls)
        defects = sum(control.nombre_defauts for control in controls)
        return LotDetails(
            lot=lot,
            controles=controls,
            total_controle=inspected,
            total_defauts=defects,
            taux_defaut_pondere=weighted_defect_rate(defects, inspected),
        )

    def add_control(self, control: ControleQualite) -> ControleQualite:
        if control.id_controle in self._controls_by_id:
            raise ValidationError(f"Le contrôle {control.id_controle} existe déjà.")
        lot = self.require_lot(control.id_lot)
        if lot.statut == "ARCHIVE":
            raise ValidationError(
                "Un contrôle ne peut pas être ajouté à un lot archivé."
            )
        control.taux_defaut = calculate_defect_rate(
            control.nombre_defauts, control.quantite_controlee
        )
        control.resultat = determine_result(control.taux_defaut, self.rules)
        validate_control(control, lot, self.rules)
        previous_status = lot.statut
        self.controls.append(control)
        self._controls_by_id[control.id_controle] = control
        self._controls_by_lot[control.id_lot].append(control)
        self._refresh_status(lot.id_lot)
        try:
            self.repository.save_controls(self.controls)
            self.repository.save_lots(self.lots)
        except Exception:
            self.controls.remove(control)
            self._controls_by_id.pop(control.id_controle, None)
            self._controls_by_lot[control.id_lot].remove(control)
            lot.statut = previous_status
            raise
        self._audit(
            "CONTROLE_AJOUTE",
            "CONTROLE",
            control.id_controle,
            f"Lot {control.id_lot}; résultat {control.resultat}",
        )
        return control

    def _refresh_status(self, lot_id: str) -> None:
        lot = self.require_lot(lot_id)
        if lot.statut != "ARCHIVE":
            lot.statut = consolidate_status(
                control.resultat for control in self._controls_by_lot.get(lot_id, [])
            )

    def repair_inconsistencies(self) -> int:
        """Recalcule uniquement les champs dérivés et retourne le nombre de corrections."""

        corrections = 0
        for control in self.controls:
            expected_rate = calculate_defect_rate(
                control.nombre_defauts, control.quantite_controlee
            )
            expected_result = determine_result(expected_rate, self.rules)
            if control.taux_defaut != expected_rate:
                control.taux_defaut = expected_rate
                corrections += 1
            if control.resultat != expected_result:
                control.resultat = expected_result
                corrections += 1
        for lot in self.lots:
            previous = lot.statut
            self._refresh_status(lot.id_lot)
            if lot.statut != previous:
                corrections += 1
        if corrections:
            self.repository.save_controls(self.controls)
            self.repository.save_lots(self.lots)
            self._audit(
                "INCOHERENCES_CORRIGEES",
                "SYSTEME",
                "DATA",
                f"{corrections} correction(s)",
            )
        return corrections

    def anomalies(self) -> list[str]:
        return detect_anomalies(self.lots, self.controls, self.rules)

    def summary(self) -> QualitySummary:
        statuses = Counter(lot.statut for lot in self.lots)
        inspected = sum(control.quantite_controlee for control in self.controls)
        defects = sum(control.nombre_defauts for control in self.controls)
        return QualitySummary(
            total_lots=len(self.lots),
            lots_conformes=statuses["CONFORME"],
            lots_a_controler=statuses["A_CONTROLER"],
            lots_rejetes=statuses["REJETE"],
            lots_sans_controle=statuses["SANS_CONTROLE"],
            lots_archives=statuses["ARCHIVE"],
            total_controles=len(self.controls),
            quantite_controlee=inspected,
            nombre_defauts=defects,
            taux_defaut_moyen=weighted_defect_rate(defects, inspected),
        )

    def next_lot_id(self, creation_date: date | None = None) -> str:
        day = (creation_date or date.today()).strftime("%Y%m%d")
        prefix = f"LOT-{day}-"
        used = [int(lot.id_lot[-3:]) for lot in self.lots if lot.id_lot.startswith(prefix)]
        return f"{prefix}{max(used, default=0) + 1:03d}"

    def next_control_id(self, control_date: date | None = None) -> str:
        day = (control_date or date.today()).strftime("%Y%m%d")
        prefix = f"QC-{day}-"
        used = [
            int(control.id_controle[-3:])
            for control in self.controls
            if control.id_controle.startswith(prefix)
        ]
        return f"{prefix}{max(used, default=0) + 1:03d}"
