"""Calculs, validations et détection des anomalies qualité."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
import re

from models import (
    AnomalieDetectee,
    ControleQualite,
    Equipement,
    IncidentEquipement,
    Lot,
    SuiviAnomalie,
    UtilisationEquipement,
)

STATUS_PRIORITY = {
    "SANS_CONTROLE": 0,
    "CONFORME": 1,
    "A_CONTROLER": 2,
    "REJETE": 3,
}


def calculate_defect_rate(defects: int, inspected: int) -> float:
    """Retourne un pourcentage de défaut arrondi à deux décimales."""

    if inspected <= 0:
        raise ValueError("La quantité contrôlée doit être strictement positive.")
    if defects < 0:
        raise ValueError("Le nombre de défauts ne peut pas être négatif.")
    return round(defects / inspected * 100, 2)


def determine_result(rate: float, rules: dict) -> str:
    """Applique les seuils actifs de la configuration à un taux de défaut."""

    thresholds = rules["thresholds"]
    if rate <= float(thresholds["conforme_max"]):
        return "CONFORME"
    if rate <= float(thresholds["a_controler_max"]):
        return "A_CONTROLER"
    return "REJETE"


def consolidate_status(results: Iterable[str]) -> str:
    """Retourne le pire résultat observé parmi les contrôles d'un lot."""

    values = list(results)
    unknown = set(values) - set(STATUS_PRIORITY)
    if unknown:
        raise ValueError(f"Résultat qualité inconnu : {', '.join(sorted(unknown))}.")
    return max(values, key=STATUS_PRIORITY.__getitem__) if values else "SANS_CONTROLE"


def weighted_defect_rate(total_defects: int, total_inspected: int) -> float:
    """Calcule l'indicateur pondéré utilisé dans les synthèses et rapports."""

    if total_inspected == 0:
        return 0.0
    return calculate_defect_rate(total_defects, total_inspected)

LOT_ID = re.compile(r"^LOT-\d{8}-\d{3}$")
CONTROL_ID = re.compile(r"^QC-\d{8}-\d{3}$")
EQUIPMENT_ID = re.compile(r"^EQ-[A-Z]{3}-\d{3}$")
ISSUE_ID = re.compile(r"^INC-\d{8}-\d{3}$")
USAGE_ID = re.compile(r"^USE-\d{8}-\d{3}$")
ANOMALY_ID = re.compile(r"^ANO-\d{8}-\d{3,6}$")
REFERENCE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,39}$")
VALID_STATUSES = {"SANS_CONTROLE", "CONFORME", "A_CONTROLER", "REJETE", "ARCHIVE"}
VALID_CONTROL_STATES = {"EN_ATTENTE", "VALIDE", "ANNULE"}
VALID_EQUIPMENT_STATUSES = {
    "DISPONIBLE",
    "EN_UTILISATION",
    "SURVEILLANCE",
    "MAINTENANCE",
    "HORS_SERVICE",
}
VALID_CRITICALITIES = {"FAIBLE", "MOYENNE", "HAUTE", "CRITIQUE"}
VALID_ISSUE_SEVERITIES = {"MINEURE", "MAJEURE", "CRITIQUE"}
VALID_ISSUE_STATUSES = {"OUVERT", "EN_COURS", "RESOLU", "CLOTURE"}
ISSUE_STATUS_TRANSITIONS = {
    "OUVERT": {"OUVERT", "EN_COURS", "RESOLU"},
    "EN_COURS": {"EN_COURS", "RESOLU"},
    "RESOLU": {"RESOLU", "CLOTURE", "OUVERT"},
    "CLOTURE": {"CLOTURE", "OUVERT"},
}
VALID_ANOMALY_STATUSES = {
    "NOUVELLE",
    "ACQUITTEE",
    "EN_COURS",
    "IGNOREE",
    "RESOLUE",
}
ANOMALY_STATUS_TRANSITIONS = {
    "NOUVELLE": {"NOUVELLE", "ACQUITTEE", "EN_COURS", "IGNOREE"},
    "ACQUITTEE": {"ACQUITTEE", "NOUVELLE", "EN_COURS", "IGNOREE"},
    "EN_COURS": {"EN_COURS", "ACQUITTEE", "IGNOREE"},
    "IGNOREE": {"IGNOREE", "NOUVELLE"},
    "RESOLUE": {"RESOLUE"},
}
VALID_ANOMALY_SEVERITIES = {"INFO", "ALERTE", "CRITIQUE"}
VALID_INTERFACE_MODES = {"EMPLOYE", "QUALITE", "MANAGER"}
REQUIRED_RULE_KEYS = {"thresholds", "production_lines", "defect_types"}


class ValidationError(ValueError):
    """Erreur métier présentable directement à l'utilisateur."""


def parse_iso_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} doit respecter le format YYYY-MM-DD.") from exc


def parse_iso_datetime(value: str, field: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"{field} doit contenir une date et une heure ISO valides."
        ) from exc


def validate_rules(rules: dict) -> None:
    """Refuse une configuration incomplète ou contradictoire."""

    missing = REQUIRED_RULE_KEYS - set(rules)
    if missing:
        raise ValidationError(f"Configuration incomplète : {', '.join(sorted(missing))}.")
    try:
        conforme = float(rules["thresholds"]["conforme_max"])
        review = float(rules["thresholds"]["a_controler_max"])
        abnormal = float(rules["thresholds"]["abnormal_rate"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Les seuils qualité doivent être numériques.") from exc
    if not 0 <= conforme < review <= abnormal <= 100:
        raise ValidationError(
            "Les seuils doivent respecter 0 <= conforme < à contrôler <= anormal <= 100."
        )
    if not rules["production_lines"] or not rules["defect_types"]:
        raise ValidationError("Les référentiels de lignes et de défauts sont obligatoires.")
    if rules.get("interface_mode", "QUALITE") not in VALID_INTERFACE_MODES:
        raise ValidationError("Le mode d'interface est inconnu.")
    for label, values in (
        ("lignes de production", rules["production_lines"]),
        ("types de défaut", rules["defect_types"]),
    ):
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not REFERENCE.fullmatch(value)
            for value in values
        ):
            raise ValidationError(
                f"Le référentiel des {label} contient une valeur invalide."
            )
        if len(values) != len(set(values)):
            raise ValidationError(f"Le référentiel des {label} contient un doublon.")


def validate_lot(lot: Lot, rules: dict) -> None:
    if not all((lot.id_lot, lot.date_creation, lot.produit, lot.ligne_production)):
        raise ValidationError("Tous les champs obligatoires du lot doivent être renseignés.")
    if not LOT_ID.fullmatch(lot.id_lot):
        raise ValidationError("L'identifiant du lot doit respecter LOT-YYYYMMDD-XXX.")
    creation = parse_iso_date(lot.date_creation, "date_creation")
    if creation > date.today():
        raise ValidationError("La date de création du lot ne peut pas être future.")
    if not REFERENCE.fullmatch(lot.produit):
        raise ValidationError(
            "La référence produit doit contenir 2 à 40 caractères majuscules, chiffres, _ ou -."
        )
    if lot.quantite_produite <= 0:
        raise ValidationError("La quantité produite doit être strictement positive.")
    if lot.ligne_production not in rules["production_lines"]:
        raise ValidationError("La ligne de production ne figure pas dans la configuration.")
    if lot.statut not in VALID_STATUSES:
        raise ValidationError("Statut de lot inconnu.")
    max_length = int(rules.get("max_comment_length", 250))
    if len(lot.commentaire) > max_length:
        raise ValidationError(f"Le commentaire est limité à {max_length} caractères.")


def validate_control(control: ControleQualite, lot: Lot, rules: dict) -> None:
    if not all((control.id_controle, control.id_lot, control.date_controle, control.type_defaut)):
        raise ValidationError(
            "Tous les champs obligatoires du contrôle doivent être renseignés."
        )
    if not CONTROL_ID.fullmatch(control.id_controle):
        raise ValidationError("L'identifiant du contrôle doit respecter QC-YYYYMMDD-XXX.")
    control_date = parse_iso_date(control.date_controle, "date_controle")
    lot_date = parse_iso_date(lot.date_creation, "date_creation")
    if control_date < lot_date:
        raise ValidationError("Le contrôle ne peut pas précéder la création du lot.")
    if control_date > date.today():
        raise ValidationError("La date du contrôle ne peut pas être future.")
    if control.quantite_controlee <= 0:
        raise ValidationError("La quantité contrôlée doit être strictement positive.")
    if control.quantite_controlee > lot.quantite_produite:
        raise ValidationError("La quantité contrôlée dépasse la quantité produite.")
    if control.nombre_defauts < 0 or control.nombre_defauts > control.quantite_controlee:
        raise ValidationError(
            "Le nombre de défauts doit être compris entre 0 et la quantité contrôlée."
        )
    if control.type_defaut not in rules["defect_types"] and control.type_defaut != "AUTRE":
        raise ValidationError("Le type de défaut ne figure pas dans la configuration.")
    if control.etat_controle not in VALID_CONTROL_STATES:
        raise ValidationError("État de contrôle inconnu.")
    max_length = int(rules.get("max_comment_length", 250))
    if len(control.commentaire) > max_length:
        raise ValidationError(f"Le commentaire est limité à {max_length} caractères.")


def validate_equipment(equipment: Equipement) -> None:
    if not all(
        (
            equipment.id_equipement,
            equipment.nom,
            equipment.categorie,
            equipment.zone,
            equipment.description,
        )
    ):
        raise ValidationError(
            "Les champs obligatoires de l'équipement doivent être renseignés."
        )
    if not EQUIPMENT_ID.fullmatch(equipment.id_equipement):
        raise ValidationError(
            "L'identifiant équipement doit respecter EQ-XXX-XXX."
        )
    if equipment.criticite not in VALID_CRITICALITIES:
        raise ValidationError("Criticité d'équipement inconnue.")
    if equipment.statut not in VALID_EQUIPMENT_STATUSES:
        raise ValidationError("Statut d'équipement inconnu.")
    if len(equipment.nom) > 80 or len(equipment.description) > 500:
        raise ValidationError("Le nom ou la description de l'équipement est trop long.")
    if equipment.guide_fichier:
        guide = Path(equipment.guide_fichier)
        if (
            guide.is_absolute()
            or ".." in guide.parts
            or guide.suffix.casefold() != ".md"
        ):
            raise ValidationError("Le chemin du guide équipement est invalide.")


def validate_equipment_issue(
    issue: IncidentEquipement, equipment: Equipement
) -> None:
    if issue.id_equipement != equipment.id_equipement:
        raise ValidationError("L'incident n'est pas rattaché au bon équipement.")
    if not ISSUE_ID.fullmatch(issue.id_incident):
        raise ValidationError("L'identifiant incident doit respecter INC-YYYYMMDD-XXX.")
    parse_iso_datetime(issue.date_signalement, "date_signalement")
    if issue.date_resolution:
        resolution = parse_iso_datetime(issue.date_resolution, "date_resolution")
        if resolution < parse_iso_datetime(
            issue.date_signalement, "date_signalement"
        ):
            raise ValidationError("La résolution ne peut pas précéder le signalement.")
    if issue.gravite not in VALID_ISSUE_SEVERITIES:
        raise ValidationError("Gravité d'incident inconnue.")
    if issue.statut not in VALID_ISSUE_STATUSES:
        raise ValidationError("Statut d'incident inconnu.")
    if not issue.categorie.strip() or not issue.description.strip():
        raise ValidationError("La catégorie et la description sont obligatoires.")
    if len(issue.description) > 500 or len(issue.action) > 500:
        raise ValidationError("La description ou l'action est limitée à 500 caractères.")


def validate_equipment_usage(
    usage: UtilisationEquipement, equipment: Equipement
) -> None:
    if usage.id_equipement != equipment.id_equipement:
        raise ValidationError("L'utilisation n'est pas rattachée au bon équipement.")
    if not USAGE_ID.fullmatch(usage.id_utilisation):
        raise ValidationError(
            "L'identifiant d'utilisation doit respecter USE-YYYYMMDD-XXX."
        )
    start = parse_iso_datetime(usage.debut, "debut")
    if usage.fin:
        end = parse_iso_datetime(usage.fin, "fin")
        if end < start:
            raise ValidationError("La fin d'utilisation ne peut pas précéder le début.")
    if not usage.utilisateur.strip():
        raise ValidationError("L'identifiant utilisateur est obligatoire.")
    if len(usage.utilisateur) > 40 or len(usage.motif) > 250:
        raise ValidationError("L'utilisateur ou le motif d'utilisation est trop long.")
    if usage.duree_minutes < 0:
        raise ValidationError("La durée d'utilisation ne peut pas être négative.")


def validate_anomaly_tracking(anomaly: SuiviAnomalie) -> None:
    if not ANOMALY_ID.fullmatch(anomaly.id_anomalie):
        raise ValidationError(
            "L'identifiant anomalie doit respecter ANO-YYYYMMDD-XXX."
        )
    if not all(
        (
            anomaly.cle_anomalie,
            anomaly.source,
            anomaly.type_anomalie,
            anomaly.entite_type,
            anomaly.entite_id,
            anomaly.description,
        )
    ):
        raise ValidationError("Le suivi d'anomalie est incomplet.")
    if anomaly.gravite not in VALID_ANOMALY_SEVERITIES:
        raise ValidationError("Gravité d'anomalie inconnue.")
    if anomaly.statut not in VALID_ANOMALY_STATUSES:
        raise ValidationError("Statut de suivi d'anomalie inconnu.")
    parse_iso_datetime(anomaly.date_detection, "date_detection")
    parse_iso_datetime(anomaly.date_mise_a_jour, "date_mise_a_jour")
    if anomaly.date_resolution:
        parse_iso_datetime(anomaly.date_resolution, "date_resolution")
    if len(anomaly.description) > 500 or len(anomaly.commentaire) > 500:
        raise ValidationError(
            "La description ou le commentaire d'anomalie est limité à 500 caractères."
        )


def detect_anomaly_details(
    lots: list[Lot], controls: list[ControleQualite], rules: dict
) -> list[AnomalieDetectee]:
    """Retourne les écarts structurés sans modifier les données."""

    anomalies: list[AnomalieDetectee] = []

    def add(
        anomaly_type: str,
        entity_type: str,
        entity_id: str,
        severity: str,
        description: str,
    ) -> None:
        anomalies.append(
            AnomalieDetectee(
                cle_anomalie=f"QUALITE:{anomaly_type}:{entity_id}",
                source="QUALITE",
                type_anomalie=anomaly_type,
                entite_type=entity_type,
                entite_id=entity_id,
                gravite=severity,
                description=description,
            )
        )

    by_lot: dict[str, list[ControleQualite]] = {lot.id_lot: [] for lot in lots}
    for control in controls:
        if control.id_lot not in by_lot:
            add(
                "CONTROLE_ORPHELIN",
                "CONTROLE",
                control.id_controle,
                "CRITIQUE",
                f"Contrôle {control.id_controle} lié à un lot inexistant ({control.id_lot})."
            )
            continue
        by_lot[control.id_lot].append(control)
        expected_rate = calculate_defect_rate(control.nombre_defauts, control.quantite_controlee)
        expected_result = determine_result(expected_rate, rules)
        if control.taux_defaut != expected_rate:
            add(
                "TAUX_INCOHERENT",
                "CONTROLE",
                control.id_controle,
                "CRITIQUE",
                f"Taux incohérent pour {control.id_controle}: "
                f"{control.taux_defaut:.2f} %, attendu {expected_rate:.2f} %.",
            )
        if control.resultat != expected_result:
            add(
                "RESULTAT_INCOHERENT",
                "CONTROLE",
                control.id_controle,
                "CRITIQUE",
                f"Résultat incohérent pour {control.id_controle}: "
                f"{control.resultat}, attendu {expected_result}.",
            )
        if (
            control.etat_controle == "VALIDE"
            and expected_rate > float(rules["thresholds"]["abnormal_rate"])
        ):
            add(
                "TAUX_ANORMAL",
                "CONTROLE",
                control.id_controle,
                "ALERTE",
                f"Taux anormal pour {control.id_controle}: {expected_rate:.2f} %.",
            )
    for lot in lots:
        linked = by_lot[lot.id_lot]
        validated = [
            control for control in linked if control.etat_controle == "VALIDE"
        ]
        if not validated and lot.statut != "ARCHIVE":
            add(
                "LOT_SANS_CONTROLE_VALIDE",
                "LOT",
                lot.id_lot,
                "ALERTE",
                f"Lot {lot.id_lot} sans contrôle qualité validé.",
            )
        expected = consolidate_status(control.resultat for control in validated)
        if lot.statut != "ARCHIVE" and lot.statut != expected:
            add(
                "STATUT_LOT_INCOHERENT",
                "LOT",
                lot.id_lot,
                "CRITIQUE",
                f"Statut incohérent pour {lot.id_lot}: {lot.statut}, attendu {expected}."
            )
    return anomalies


def detect_anomalies(
    lots: list[Lot], controls: list[ControleQualite], rules: dict
) -> list[str]:
    """Retourne les messages courts utilisés par la console."""

    return [
        anomaly.description
        for anomaly in detect_anomaly_details(lots, controls, rules)
    ]
