"""Cas d'usage et règles de gestion de l'application."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date, datetime
import logging
from pathlib import Path
import re

from models import (
    AnomalieDetectee,
    ControleQualite,
    Equipement,
    IncidentEquipement,
    Lot,
    LotDetails,
    QualitySummary,
    SuiviAnomalie,
    UtilisationEquipement,
)
from quality_rules import (
    VALID_ANOMALY_STATUSES,
    VALID_ISSUE_STATUSES,
    ValidationError,
    calculate_defect_rate,
    consolidate_status,
    detect_anomalies,
    detect_anomaly_details,
    determine_result,
    parse_iso_datetime,
    validate_anomaly_tracking,
    validate_control,
    validate_equipment,
    validate_equipment_issue,
    validate_equipment_usage,
    validate_lot,
    validate_rules,
    weighted_defect_rate,
)
from storage import CsvRepository, StorageError

LOGGER = logging.getLogger(__name__)


class TraceabilityService:
    def __init__(self, root: Path) -> None:
        self.repository = CsvRepository(root)
        self.rules = self.repository.load_rules()
        mode_was_missing = "interface_mode" not in self.rules
        self.rules.setdefault("interface_mode", "QUALITE")
        validate_rules(self.rules)
        if mode_was_missing:
            self.repository.save_rules(self.rules)
        self.lots = self.repository.load_lots()
        self.controls = self.repository.load_controls()
        self.equipment = self.repository.load_equipment()
        self.equipment_issues = self.repository.load_equipment_issues()
        self.equipment_usage = self.repository.load_equipment_usage()
        self.anomaly_tracking = self.repository.load_anomaly_tracking()
        self._rebuild_indexes()
        self._validate_loaded_data()
        self.synchronize_anomalies()

    def _rebuild_indexes(self) -> None:
        self._lots_by_id = {lot.id_lot: lot for lot in self.lots}
        self._controls_by_id = {control.id_controle: control for control in self.controls}
        self._controls_by_lot: dict[str, list[ControleQualite]] = defaultdict(list)
        for control in self.controls:
            self._controls_by_lot[control.id_lot].append(control)
        self._equipment_by_id = {
            item.id_equipement: item for item in self.equipment
        }
        self._issues_by_id = {
            issue.id_incident: issue for issue in self.equipment_issues
        }
        self._issues_by_equipment: dict[str, list[IncidentEquipement]] = defaultdict(list)
        for issue in self.equipment_issues:
            self._issues_by_equipment[issue.id_equipement].append(issue)
        self._usage_by_id = {
            usage.id_utilisation: usage for usage in self.equipment_usage
        }
        self._usage_by_equipment: dict[
            str, list[UtilisationEquipement]
        ] = defaultdict(list)
        for usage in self.equipment_usage:
            self._usage_by_equipment[usage.id_equipement].append(usage)
        self._anomalies_by_id = {
            anomaly.id_anomalie: anomaly for anomaly in self.anomaly_tracking
        }
        self._anomalies_by_key = {
            anomaly.cle_anomalie: anomaly for anomaly in self.anomaly_tracking
        }
        if len(self._lots_by_id) != len(self.lots):
            raise ValidationError("Le fichier lots.csv contient un identifiant dupliqué.")
        if len(self._controls_by_id) != len(self.controls):
            raise ValidationError("Le fichier controls.csv contient un identifiant dupliqué.")
        if len(self._equipment_by_id) != len(self.equipment):
            raise ValidationError("Le fichier equipment.csv contient un identifiant dupliqué.")
        if len(self._issues_by_id) != len(self.equipment_issues):
            raise ValidationError(
                "Le fichier equipment_issues.csv contient un identifiant dupliqué."
            )
        if len(self._usage_by_id) != len(self.equipment_usage):
            raise ValidationError(
                "Le fichier equipment_usage.csv contient un identifiant dupliqué."
            )
        if len(self._anomalies_by_id) != len(self.anomaly_tracking):
            raise ValidationError(
                "Le fichier anomaly_tracking.csv contient un identifiant dupliqué."
            )
        if len(self._anomalies_by_key) != len(self.anomaly_tracking):
            raise ValidationError(
                "Le fichier anomaly_tracking.csv contient une clé de détection dupliquée."
            )

    def _validate_loaded_data(self) -> None:
        for lot in self.lots:
            validate_lot(lot, self.rules)
        for control in self.controls:
            lot = self._lots_by_id.get(control.id_lot)
            if lot is not None:
                validate_control(control, lot, self.rules)
        for equipment in self.equipment:
            validate_equipment(equipment)
        for issue in self.equipment_issues:
            equipment = self._equipment_by_id.get(issue.id_equipement)
            if equipment is not None:
                validate_equipment_issue(issue, equipment)
        for usage in self.equipment_usage:
            equipment = self._equipment_by_id.get(usage.id_equipement)
            if equipment is not None:
                validate_equipment_usage(usage, equipment)
        for anomaly in self.anomaly_tracking:
            validate_anomaly_tracking(anomaly)

    def _audit(self, event: str, entity_type: str, entity_id: str, details: str = "") -> None:
        try:
            self.repository.record_event(
                event,
                entity_type,
                entity_id,
                details,
                profile=self.rules.get("interface_mode", "SYSTEME"),
            )
        except StorageError as exc:
            # Une indisponibilité du journal ne doit pas annuler une donnée déjà
            # sauvegardée. Elle reste visible dans le log technique.
            LOGGER.warning("Événement d'audit non enregistré : %s", exc)

    def get_equipment(self, equipment_id: str) -> Equipement | None:
        return self._equipment_by_id.get(equipment_id)

    def require_equipment(self, equipment_id: str) -> Equipement:
        equipment = self.get_equipment(equipment_id)
        if equipment is None:
            raise ValidationError(f"Équipement {equipment_id} introuvable.")
        return equipment

    def create_equipment(self, equipment: Equipement) -> Equipement:
        if self.get_equipment(equipment.id_equipement):
            raise ValidationError(
                f"L'équipement {equipment.id_equipement} existe déjà."
            )
        validate_equipment(equipment)
        self.equipment.append(equipment)
        self._equipment_by_id[equipment.id_equipement] = equipment
        try:
            self.repository.save_equipment(self.equipment)
        except Exception:
            self.equipment.remove(equipment)
            self._equipment_by_id.pop(equipment.id_equipement, None)
            raise
        self._audit(
            "EQUIPEMENT_CREE",
            "EQUIPEMENT",
            equipment.id_equipement,
            equipment.nom,
        )
        return equipment

    def update_equipment(
        self, equipment_id: str, **changes: object
    ) -> Equipement:
        equipment = self.require_equipment(equipment_id)
        allowed = {
            "nom",
            "categorie",
            "zone",
            "criticite",
            "statut",
            "description",
            "guide_fichier",
            "commentaire",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValidationError(
                f"Champ de modification inconnu : {', '.join(sorted(unknown))}."
            )
        requested_status = changes.get("statut", equipment.statut)
        if (
            self.active_equipment_usage(equipment_id)
            and requested_status != "EN_UTILISATION"
        ):
            raise ValidationError(
                "Terminez l'utilisation en cours avant de modifier le statut."
            )
        active_issues = [
            issue
            for issue in self._issues_by_equipment.get(equipment_id, [])
            if issue.statut in {"OUVERT", "EN_COURS"}
        ]
        if (
            any(issue.gravite == "CRITIQUE" for issue in active_issues)
            and requested_status != "HORS_SERVICE"
        ):
            raise ValidationError(
                "Un incident critique ouvert impose le statut HORS_SERVICE."
            )
        if (
            any(issue.gravite == "MAJEURE" for issue in active_issues)
            and requested_status == "DISPONIBLE"
        ):
            raise ValidationError(
                "Un incident majeur ouvert impose au minimum le statut SURVEILLANCE."
            )
        original = replace(equipment)
        try:
            for field, value in changes.items():
                if value is not None:
                    setattr(equipment, field, value)
            validate_equipment(equipment)
            self.repository.save_equipment(self.equipment)
        except Exception:
            for field, value in original.to_dict().items():
                setattr(equipment, field, value)
            raise
        self._audit(
            "EQUIPEMENT_MODIFIE",
            "EQUIPEMENT",
            equipment.id_equipement,
            equipment.nom,
        )
        return equipment

    def equipment_issues_for(
        self, equipment_id: str
    ) -> list[IncidentEquipement]:
        self.require_equipment(equipment_id)
        return list(self._issues_by_equipment.get(equipment_id, []))

    def equipment_usage_for(
        self, equipment_id: str
    ) -> list[UtilisationEquipement]:
        self.require_equipment(equipment_id)
        return list(self._usage_by_equipment.get(equipment_id, []))

    def open_equipment_issues(self) -> list[IncidentEquipement]:
        return [
            issue
            for issue in self.equipment_issues
            if issue.statut in {"OUVERT", "EN_COURS"}
        ]

    def require_equipment_issue(self, issue_id: str) -> IncidentEquipement:
        issue = self._issues_by_id.get(issue_id)
        if issue is None:
            raise ValidationError(f"Incident {issue_id} introuvable.")
        return issue

    def active_equipment_usage(
        self, equipment_id: str
    ) -> UtilisationEquipement | None:
        self.require_equipment(equipment_id)
        return next(
            (
                usage
                for usage in reversed(
                    self._usage_by_equipment.get(equipment_id, [])
                )
                if not usage.fin
            ),
            None,
        )

    def _refresh_equipment_status(self, equipment_id: str) -> None:
        equipment = self.require_equipment(equipment_id)
        active_issues = [
            issue
            for issue in self._issues_by_equipment.get(equipment_id, [])
            if issue.statut in {"OUVERT", "EN_COURS"}
        ]
        if any(issue.gravite == "CRITIQUE" for issue in active_issues):
            equipment.statut = "HORS_SERVICE"
        elif any(issue.gravite == "MAJEURE" for issue in active_issues):
            equipment.statut = "SURVEILLANCE"
        elif self.active_equipment_usage(equipment_id):
            equipment.statut = "EN_UTILISATION"
        else:
            equipment.statut = "DISPONIBLE"

    def report_equipment_issue(
        self, issue: IncidentEquipement
    ) -> IncidentEquipement:
        if issue.id_incident in self._issues_by_id:
            raise ValidationError(f"L'incident {issue.id_incident} existe déjà.")
        equipment = self.require_equipment(issue.id_equipement)
        validate_equipment_issue(issue, equipment)
        previous_status = equipment.statut
        self.equipment_issues.append(issue)
        self._issues_by_id[issue.id_incident] = issue
        self._issues_by_equipment[issue.id_equipement].append(issue)
        self._refresh_equipment_status(equipment.id_equipement)
        try:
            self.repository.save_equipment_issues(self.equipment_issues)
            self.repository.save_equipment(self.equipment)
        except Exception:
            self.equipment_issues.remove(issue)
            self._issues_by_id.pop(issue.id_incident, None)
            self._issues_by_equipment[issue.id_equipement].remove(issue)
            equipment.statut = previous_status
            raise
        self._audit(
            "INCIDENT_SIGNALE",
            "EQUIPEMENT",
            equipment.id_equipement,
            f"{issue.id_incident}; gravité {issue.gravite}",
        )
        return issue

    def update_equipment_issue(
        self, issue_id: str, *, statut: str, action: str = ""
    ) -> IncidentEquipement:
        issue = self.require_equipment_issue(issue_id)
        if statut not in VALID_ISSUE_STATUSES:
            raise ValidationError("Statut d'incident inconnu.")
        if statut in {"RESOLU", "CLOTURE"} and not action.strip():
            raise ValidationError(
                "Une action réalisée est requise pour résoudre ou clôturer l'incident."
            )
        equipment = self.require_equipment(issue.id_equipement)
        original = replace(issue)
        previous_status = equipment.statut
        issue.statut = statut
        issue.action = action.strip()
        issue.date_resolution = (
            datetime.now().astimezone().isoformat(timespec="seconds")
            if statut in {"RESOLU", "CLOTURE"}
            else ""
        )
        try:
            validate_equipment_issue(issue, equipment)
            self._refresh_equipment_status(equipment.id_equipement)
            self.repository.save_equipment_issues(self.equipment_issues)
            self.repository.save_equipment(self.equipment)
        except Exception:
            for field, value in original.to_dict().items():
                setattr(issue, field, value)
            equipment.statut = previous_status
            raise
        self._audit(
            "INCIDENT_MIS_A_JOUR",
            "INCIDENT",
            issue.id_incident,
            f"Statut {issue.statut}",
        )
        return issue

    def start_equipment_usage(
        self,
        equipment_id: str,
        utilisateur: str,
        motif: str = "",
        started_at: datetime | None = None,
    ) -> UtilisationEquipement:
        equipment = self.require_equipment(equipment_id)
        if self.active_equipment_usage(equipment_id):
            raise ValidationError("Une utilisation est déjà en cours.")
        if equipment.statut not in {"DISPONIBLE", "SURVEILLANCE"}:
            raise ValidationError(
                f"L'équipement est {equipment.statut.replace('_', ' ').lower()}."
            )
        moment = started_at or datetime.now().astimezone()
        usage = UtilisationEquipement(
            id_utilisation=self.next_usage_id(moment.date()),
            id_equipement=equipment_id,
            debut=moment.isoformat(timespec="seconds"),
            fin="",
            utilisateur=utilisateur.strip().upper(),
            motif=motif.strip(),
        )
        validate_equipment_usage(usage, equipment)
        previous_status = equipment.statut
        self.equipment_usage.append(usage)
        self._usage_by_id[usage.id_utilisation] = usage
        self._usage_by_equipment[equipment_id].append(usage)
        equipment.statut = "EN_UTILISATION"
        try:
            self.repository.save_equipment_usage(self.equipment_usage)
            self.repository.save_equipment(self.equipment)
        except Exception:
            self.equipment_usage.remove(usage)
            self._usage_by_id.pop(usage.id_utilisation, None)
            self._usage_by_equipment[equipment_id].remove(usage)
            equipment.statut = previous_status
            raise
        self._audit(
            "UTILISATION_DEMARREE",
            "EQUIPEMENT",
            equipment_id,
            f"{usage.id_utilisation}; utilisateur {usage.utilisateur}",
        )
        return usage

    def end_equipment_usage(
        self, equipment_id: str, ended_at: datetime | None = None
    ) -> UtilisationEquipement:
        equipment = self.require_equipment(equipment_id)
        usage = self.active_equipment_usage(equipment_id)
        if usage is None:
            raise ValidationError("Aucune utilisation n'est en cours.")
        original = replace(usage)
        previous_status = equipment.statut
        end = ended_at or datetime.now().astimezone()
        start = parse_iso_datetime(usage.debut, "debut")
        if start.tzinfo is not None and end.tzinfo is None:
            end = end.replace(tzinfo=start.tzinfo)
        elif start.tzinfo is None and end.tzinfo is not None:
            end = end.replace(tzinfo=None)
        usage.fin = end.isoformat(timespec="seconds")
        usage.duree_minutes = max(0, round((end - start).total_seconds() / 60))
        try:
            validate_equipment_usage(usage, equipment)
            self._refresh_equipment_status(equipment_id)
            self.repository.save_equipment_usage(self.equipment_usage)
            self.repository.save_equipment(self.equipment)
        except Exception:
            for field, value in original.to_dict().items():
                setattr(usage, field, value)
            equipment.statut = previous_status
            raise
        self._audit(
            "UTILISATION_TERMINEE",
            "EQUIPEMENT",
            equipment_id,
            f"{usage.id_utilisation}; {usage.duree_minutes} minute(s)",
        )
        return usage

    def equipment_guide_path(self, equipment_id: str) -> Path | None:
        equipment = self.require_equipment(equipment_id)
        if not equipment.guide_fichier:
            return None
        path = (self.repository.root / equipment.guide_fichier).resolve()
        guides_root = (
            self.repository.root / "docs" / "equipment-guides"
        ).resolve()
        if guides_root not in path.parents or not path.is_file():
            raise ValidationError("Le guide associé est introuvable ou invalide.")
        return path

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
            control.resultat
            for control in self.controls_for_lot(lot_id)
            if control.etat_controle == "VALIDE"
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
                lot for lot in self.lots if query in str(getattr(lot, allowed[field])).casefold()
            ]
        return [
            lot
            for lot in self.lots
            if any(query in str(value).casefold() for value in lot.to_dict().values())
        ]

    def controls_for_lot(self, lot_id: str) -> list[ControleQualite]:
        self.require_lot(lot_id)
        return list(self._controls_by_lot.get(lot_id, []))

    def get_control(self, control_id: str) -> ControleQualite | None:
        return self._controls_by_id.get(control_id)

    def require_control(self, control_id: str) -> ControleQualite:
        control = self.get_control(control_id)
        if control is None:
            raise ValidationError(f"Contrôle {control_id} introuvable.")
        return control

    def lot_details(self, lot_id: str) -> LotDetails:
        lot = self.require_lot(lot_id)
        controls = tuple(self.controls_for_lot(lot_id))
        validated = [
            control for control in controls if control.etat_controle == "VALIDE"
        ]
        inspected = sum(control.quantite_controlee for control in validated)
        defects = sum(control.nombre_defauts for control in validated)
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
            raise ValidationError("Un contrôle ne peut pas être ajouté à un lot archivé.")
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

    def update_control(self, control_id: str, **changes: object) -> ControleQualite:
        """Modifie un contrôle et recalcule ses champs qualité dérivés."""

        control = self.require_control(control_id)
        lot = self.require_lot(control.id_lot)
        if lot.statut == "ARCHIVE":
            raise ValidationError("Un contrôle d'un lot archivé ne peut pas être modifié.")
        allowed = {
            "date_controle",
            "quantite_controlee",
            "nombre_defauts",
            "type_defaut",
            "commentaire",
            "etat_controle",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValidationError(
                f"Champ de modification inconnu : {', '.join(sorted(unknown))}."
            )
        original = replace(control)
        previous_status = lot.statut
        try:
            for field, value in changes.items():
                if value is not None:
                    setattr(control, field, value)
            control.taux_defaut = calculate_defect_rate(
                control.nombre_defauts, control.quantite_controlee
            )
            control.resultat = determine_result(control.taux_defaut, self.rules)
            validate_control(control, lot, self.rules)
            self._refresh_status(lot.id_lot)
            self.repository.save_controls(self.controls)
            self.repository.save_lots(self.lots)
        except Exception:
            for field, value in original.to_dict().items():
                setattr(control, field, value)
            lot.statut = previous_status
            raise
        changed = [
            field
            for field, value in control.to_dict().items()
            if value != original.to_dict()[field]
        ]
        self._audit(
            "CONTROLE_MODIFIE",
            "CONTROLE",
            control.id_controle,
            f"Champs : {', '.join(changed) if changed else 'aucun'}",
        )
        return control

    def _refresh_status(self, lot_id: str) -> None:
        lot = self.require_lot(lot_id)
        if lot.statut != "ARCHIVE":
            lot.statut = consolidate_status(
                control.resultat
                for control in self._controls_by_lot.get(lot_id, [])
                if control.etat_controle == "VALIDE"
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
                "INCOHERENCES_CORRIGEES", "SYSTEME", "DATA", f"{corrections} correction(s)"
            )
        self.synchronize_anomalies()
        return corrections

    def update_rules(self, next_rules: dict) -> int:
        """Valide les seuils, les sauvegarde et recalcule les champs dérivés."""

        validate_rules(next_rules)
        used_lines = {lot.ligne_production for lot in self.lots}
        missing_lines = used_lines - set(next_rules["production_lines"])
        used_defects = {
            control.type_defaut
            for control in self.controls
            if control.type_defaut != "AUTRE"
        }
        missing_defects = used_defects - set(next_rules["defect_types"])
        if missing_lines or missing_defects:
            details = []
            if missing_lines:
                details.append(f"lignes utilisées : {', '.join(sorted(missing_lines))}")
            if missing_defects:
                details.append(
                    f"types utilisés : {', '.join(sorted(missing_defects))}"
                )
            raise ValidationError(
                "Impossible de retirer des valeurs encore référencées ("
                + "; ".join(details)
                + ")."
            )
        previous_rules = self.rules
        previous_controls = [
            (control, control.taux_defaut, control.resultat)
            for control in self.controls
        ]
        previous_statuses = [(lot, lot.statut) for lot in self.lots]
        configuration_saved = False
        try:
            self.repository.save_rules(next_rules)
            configuration_saved = True
            self.rules = next_rules
            corrections = self.repair_inconsistencies()
        except Exception:
            self.rules = previous_rules
            for control, rate, result in previous_controls:
                control.taux_defaut = rate
                control.resultat = result
            for lot, status in previous_statuses:
                lot.statut = status
            if configuration_saved:
                try:
                    self.repository.save_rules(previous_rules)
                    self.repository.save_controls(self.controls)
                    self.repository.save_lots(self.lots)
                except StorageError:
                    LOGGER.exception(
                        "Restauration automatique de la configuration incomplète"
                    )
            raise
        self._audit(
            "REGLES_MODIFIEES",
            "CONFIGURATION",
            "QUALITY_RULES",
            f"{corrections} champ(s) dérivé(s) recalculé(s)",
        )
        return corrections

    def anomalies(self) -> list[str]:
        return detect_anomalies(self.lots, self.controls, self.rules)

    def anomaly_details(self) -> list[AnomalieDetectee]:
        return detect_anomaly_details(self.lots, self.controls, self.rules)

    def synchronize_anomalies(self) -> list[SuiviAnomalie]:
        """Crée, réouvre ou résout les suivis selon la détection actuelle."""

        detected = {
            anomaly.cle_anomalie: anomaly for anomaly in self.anomaly_details()
        }
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        changed = False
        created = 0
        reopened = 0
        resolved = 0

        for key, current in detected.items():
            tracked = self._anomalies_by_key.get(key)
            if tracked is None:
                tracked = SuiviAnomalie(
                    id_anomalie=self.next_anomaly_id(),
                    cle_anomalie=current.cle_anomalie,
                    source=current.source,
                    type_anomalie=current.type_anomalie,
                    entite_type=current.entite_type,
                    entite_id=current.entite_id,
                    gravite=current.gravite,
                    description=current.description,
                    statut="NOUVELLE",
                    commentaire="",
                    date_detection=now,
                    date_mise_a_jour=now,
                )
                validate_anomaly_tracking(tracked)
                self.anomaly_tracking.append(tracked)
                self._anomalies_by_id[tracked.id_anomalie] = tracked
                self._anomalies_by_key[key] = tracked
                changed = True
                created += 1
                continue

            technical_changed = any(
                (
                    tracked.source != current.source,
                    tracked.type_anomalie != current.type_anomalie,
                    tracked.entite_type != current.entite_type,
                    tracked.entite_id != current.entite_id,
                    tracked.gravite != current.gravite,
                    tracked.description != current.description,
                )
            )
            if technical_changed:
                tracked.source = current.source
                tracked.type_anomalie = current.type_anomalie
                tracked.entite_type = current.entite_type
                tracked.entite_id = current.entite_id
                tracked.gravite = current.gravite
                tracked.description = current.description
                tracked.date_mise_a_jour = now
                changed = True
            if tracked.statut == "RESOLUE":
                tracked.statut = "NOUVELLE"
                tracked.date_resolution = ""
                tracked.date_mise_a_jour = now
                changed = True
                reopened += 1

        for tracked in self.anomaly_tracking:
            if (
                tracked.cle_anomalie not in detected
                and tracked.statut != "RESOLUE"
            ):
                tracked.statut = "RESOLUE"
                tracked.date_resolution = now
                tracked.date_mise_a_jour = now
                changed = True
                resolved += 1

        if changed:
            self.repository.save_anomaly_tracking(self.anomaly_tracking)
            self._audit(
                "ANOMALIES_SYNCHRONISEES",
                "SYSTEME",
                "ANOMALIES",
                (
                    f"{created} créée(s); {reopened} réouverte(s); "
                    f"{resolved} résolue(s)"
                ),
            )
        return list(self.anomaly_tracking)

    def tracked_anomalies(
        self,
        *,
        include_resolved: bool = True,
        include_ignored: bool = True,
    ) -> list[SuiviAnomalie]:
        self.synchronize_anomalies()
        return [
            anomaly
            for anomaly in self.anomaly_tracking
            if (include_resolved or anomaly.statut != "RESOLUE")
            and (include_ignored or anomaly.statut != "IGNOREE")
        ]

    def active_tracked_anomalies(self) -> list[SuiviAnomalie]:
        return [
            anomaly
            for anomaly in self.tracked_anomalies(
                include_resolved=False, include_ignored=False
            )
        ]

    def require_tracked_anomaly(self, anomaly_id: str) -> SuiviAnomalie:
        anomaly = self._anomalies_by_id.get(anomaly_id)
        if anomaly is None:
            raise ValidationError(f"Anomalie {anomaly_id} introuvable.")
        return anomaly

    def update_anomaly_tracking(
        self, anomaly_id: str, *, statut: str, commentaire: str = ""
    ) -> SuiviAnomalie:
        """Met à jour le traitement humain sans altérer la détection technique."""

        anomaly = self.require_tracked_anomaly(anomaly_id)
        if statut not in VALID_ANOMALY_STATUSES:
            raise ValidationError("Statut de suivi d'anomalie inconnu.")
        comment = commentaire.strip()
        if statut == "IGNOREE" and not comment:
            raise ValidationError(
                "Un motif est obligatoire pour retirer une anomalie de la vue active."
            )
        current_keys = {
            item.cle_anomalie for item in self.anomaly_details()
        }
        if statut == "RESOLUE" and anomaly.cle_anomalie in current_keys:
            raise ValidationError(
                "La cause est encore présente. Corrigez d'abord la donnée concernée, "
                "ou classez l'anomalie comme ignorée en indiquant pourquoi."
            )
        original = replace(anomaly)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        anomaly.statut = statut
        anomaly.commentaire = comment
        anomaly.date_mise_a_jour = now
        anomaly.date_resolution = now if statut == "RESOLUE" else ""
        try:
            validate_anomaly_tracking(anomaly)
            self.repository.save_anomaly_tracking(self.anomaly_tracking)
        except Exception:
            for field, value in original.to_dict().items():
                setattr(anomaly, field, value)
            raise
        self._audit(
            "ANOMALIE_MISE_A_JOUR",
            "ANOMALIE",
            anomaly.id_anomalie,
            f"Statut {anomaly.statut}; {anomaly.commentaire}",
        )
        return anomaly

    def summary(self) -> QualitySummary:
        statuses = Counter(lot.statut for lot in self.lots)
        validated = [
            control for control in self.controls if control.etat_controle == "VALIDE"
        ]
        inspected = sum(control.quantite_controlee for control in validated)
        defects = sum(control.nombre_defauts for control in validated)
        return QualitySummary(
            total_lots=len(self.lots),
            lots_conformes=statuses["CONFORME"],
            lots_a_controler=statuses["A_CONTROLER"],
            lots_rejetes=statuses["REJETE"],
            lots_sans_controle=statuses["SANS_CONTROLE"],
            lots_archives=statuses["ARCHIVE"],
            total_controles=len(validated),
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

    def next_equipment_id(self, category_code: str = "GEN") -> str:
        code = re.sub(r"[^A-Z]", "", category_code.upper())[:3].ljust(3, "X")
        prefix = f"EQ-{code}-"
        used = [
            int(item.id_equipement[-3:])
            for item in self.equipment
            if item.id_equipement.startswith(prefix)
        ]
        return f"{prefix}{max(used, default=0) + 1:03d}"

    def next_issue_id(self, issue_date: date | None = None) -> str:
        day = (issue_date or date.today()).strftime("%Y%m%d")
        prefix = f"INC-{day}-"
        used = [
            int(item.id_incident[-3:])
            for item in self.equipment_issues
            if item.id_incident.startswith(prefix)
        ]
        return f"{prefix}{max(used, default=0) + 1:03d}"

    def next_usage_id(self, usage_date: date | None = None) -> str:
        day = (usage_date or date.today()).strftime("%Y%m%d")
        prefix = f"USE-{day}-"
        used = [
            int(item.id_utilisation[-3:])
            for item in self.equipment_usage
            if item.id_utilisation.startswith(prefix)
        ]
        return f"{prefix}{max(used, default=0) + 1:03d}"

    def next_anomaly_id(self, anomaly_date: date | None = None) -> str:
        day = (anomaly_date or date.today()).strftime("%Y%m%d")
        prefix = f"ANO-{day}-"
        used = [
            int(item.id_anomalie[-3:])
            for item in self.anomaly_tracking
            if item.id_anomalie.startswith(prefix)
        ]
        return f"{prefix}{max(used, default=0) + 1:03d}"
