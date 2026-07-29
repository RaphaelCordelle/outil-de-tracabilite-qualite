"""Calculs et décisions qualité configurables."""

from __future__ import annotations

from collections.abc import Iterable

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
    """Applique les seuils actifs à un taux de défaut."""

    thresholds = rules["thresholds"]
    if rate <= float(thresholds["conforme_max"]):
        return "CONFORME"
    if rate <= float(thresholds["a_controler_max"]):
        return "A_CONTROLER"
    return "REJETE"


def consolidate_status(results: Iterable[str]) -> str:
    """Retourne le pire résultat observé ou SANS_CONTROLE."""

    values = list(results)
    unknown = set(values) - set(STATUS_PRIORITY)
    if unknown:
        raise ValueError(f"Résultat qualité inconnu : {', '.join(sorted(unknown))}.")
    return max(values, key=STATUS_PRIORITY.__getitem__) if values else "SANS_CONTROLE"


def weighted_defect_rate(total_defects: int, total_inspected: int) -> float:
    """Calcule l'indicateur pondéré utilisé dans les synthèses."""

    if total_inspected == 0:
        return 0.0
    return calculate_defect_rate(total_defects, total_inspected)
