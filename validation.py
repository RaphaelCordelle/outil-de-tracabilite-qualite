"""Validation des saisies, de la configuration et des incohérences."""

from datetime import date
import re

from models import ControleQualite, Lot
from quality_rules import calculate_defect_rate, consolidate_status, determine_result

LOT_ID = re.compile(r"^LOT-\d{8}-\d{3}$")
CONTROL_ID = re.compile(r"^QC-\d{8}-\d{3}$")
REFERENCE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,39}$")
VALID_STATUSES = {"SANS_CONTROLE", "CONFORME", "A_CONTROLER", "REJETE", "ARCHIVE"}
REQUIRED_RULE_KEYS = {"thresholds", "production_lines", "defect_types"}


class ValidationError(ValueError):
    """Erreur métier présentable directement à l'utilisateur."""


def parse_iso_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} doit respecter le format YYYY-MM-DD.") from exc


def validate_rules(rules: dict) -> None:
    """Refuse une configuration incomplète ou contradictoire."""

    missing = REQUIRED_RULE_KEYS - set(rules)
    if missing:
        raise ValidationError(
            f"Configuration incomplète : {', '.join(sorted(missing))}."
        )
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
        raise ValidationError("Tous les champs obligatoires du contrôle doivent être renseignés.")
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
    max_length = int(rules.get("max_comment_length", 250))
    if len(control.commentaire) > max_length:
        raise ValidationError(f"Le commentaire est limité à {max_length} caractères.")


def detect_anomalies(
    lots: list[Lot], controls: list[ControleQualite], rules: dict
) -> list[str]:
    """Retourne toutes les alertes sans modifier les données."""

    anomalies: list[str] = []
    by_lot = {lot.id_lot: [] for lot in lots}
    for control in controls:
        if control.id_lot not in by_lot:
            anomalies.append(
                f"Contrôle {control.id_controle} lié à un lot inexistant ({control.id_lot})."
            )
            continue
        by_lot[control.id_lot].append(control)
        expected_rate = calculate_defect_rate(
            control.nombre_defauts, control.quantite_controlee
        )
        expected_result = determine_result(expected_rate, rules)
        if control.taux_defaut != expected_rate:
            anomalies.append(
                f"Taux incohérent pour {control.id_controle}: "
                f"{control.taux_defaut:.2f} %, attendu {expected_rate:.2f} %."
            )
        if control.resultat != expected_result:
            anomalies.append(
                f"Résultat incohérent pour {control.id_controle}: "
                f"{control.resultat}, attendu {expected_result}."
            )
        if expected_rate > float(rules["thresholds"]["abnormal_rate"]):
            anomalies.append(
                f"Taux anormal pour {control.id_controle}: {expected_rate:.2f} %."
            )
    for lot in lots:
        linked = by_lot[lot.id_lot]
        if not linked and lot.statut != "ARCHIVE":
            anomalies.append(f"Lot {lot.id_lot} sans contrôle qualité.")
        expected = consolidate_status(control.resultat for control in linked)
        if lot.statut != "ARCHIVE" and lot.statut != expected:
            anomalies.append(
                f"Statut incohérent pour {lot.id_lot}: {lot.statut}, attendu {expected}."
            )
    return anomalies
