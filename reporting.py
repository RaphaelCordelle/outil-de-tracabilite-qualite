"""Génération du rapport qualité au format Markdown."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from models import (
    ControleQualite,
    Equipement,
    IncidentEquipement,
    Lot,
    SuiviAnomalie,
    UtilisationEquipement,
)
from quality_rules import detect_anomalies, weighted_defect_rate

DISCLAIMER = "Données fictives utilisées uniquement pour présenter le projet."
LOT_STATUS_LABELS = {
    "A_CONTROLER": "À contrôler",
    "REJETE": "Rejeté",
}
REPORT_LABELS = {
    "SOUDURE_FROIDE": "Soudure froide",
    "COMPOSANT_ABSENT": "Composant absent",
    "POLARITE_INVERSEE": "Polarité inversée",
    "DEFAUT_VISUEL": "Défaut visuel",
    "TEST_ELECTRIQUE": "Test électrique",
    "MINEURE": "Mineure",
    "MAJEURE": "Majeure",
    "CRITIQUE": "Critique",
    "OUVERT": "Ouvert",
    "EN_COURS": "En cours",
}


def _percent(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}".replace(".", ",") + " %"


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\r\n", "<br>").replace("\n", "<br>")


def _markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend(
        "| " + " | ".join(_markdown_cell(value) for value in row) + " |"
        for row in rows
    )
    return lines


def generate_report(
    root: Path,
    lots: list[Lot],
    controls: list[ControleQualite],
    rules: dict,
    equipment: list[Equipement] | None = None,
    equipment_issues: list[IncidentEquipement] | None = None,
    equipment_usage: list[UtilisationEquipement] | None = None,
    anomaly_tracking: list[SuiviAnomalie] | None = None,
) -> Path:
    """Génère un rapport Markdown à partir des données courantes."""

    now = datetime.now().astimezone()
    equipment = equipment or []
    equipment_issues = equipment_issues or []
    equipment_usage = equipment_usage or []
    anomaly_tracking = anomaly_tracking or []
    validated_controls = [
        item for item in controls if item.etat_controle == "VALIDE"
    ]
    total_inspected = sum(item.quantite_controlee for item in validated_controls)
    total_defects = sum(item.nombre_defauts for item in validated_controls)
    weighted_rate = weighted_defect_rate(total_defects, total_inspected)
    statuses = Counter(lot.statut for lot in lots)
    anomalies = detect_anomalies(lots, controls, rules)
    non_archived = [lot for lot in lots if lot.statut != "ARCHIVE"]
    controlled_ids = {control.id_lot for control in validated_controls}
    coverage = (
        round(
            sum(lot.id_lot in controlled_ids for lot in non_archived)
            / len(non_archived)
            * 100,
            1,
        )
        if non_archived
        else 0.0
    )
    non_conforming = [lot for lot in lots if lot.statut in {"A_CONTROLER", "REJETE"}]

    defect_totals: Counter[str] = Counter()
    mode = rules.get("frequent_defects_mode", "total_defects")
    for item in validated_controls:
        defect_totals[item.type_defaut] += 1 if mode == "occurrences" else item.nombre_defauts

    by_line: dict[str, list[ControleQualite]] = {}
    lots_by_id = {lot.id_lot: lot for lot in lots}
    for control in validated_controls:
        lot = lots_by_id.get(control.id_lot)
        if lot:
            by_line.setdefault(lot.ligne_production, []).append(control)

    lines = [
        "# Suivi qualité",
        "",
        f"Mis à jour le {now:%d/%m/%Y à %H:%M}",
        "",
        DISCLAIMER,
        "",
        "## Situation générale",
        "",
    ]
    summary_rows = [
        ["Lots suivis", len(lots)],
        ["Conformes", statuses["CONFORME"]],
        ["À contrôler", statuses["A_CONTROLER"]],
        ["Rejetés", statuses["REJETE"]],
        ["Sans contrôle", statuses["SANS_CONTROLE"]],
        ["Contrôles validés", len(validated_controls)],
        ["Quantité contrôlée", total_inspected],
        ["Défauts relevés", total_defects],
        ["Lots contrôlés", _percent(coverage, 1)],
        ["Taux de défaut pondéré", _percent(weighted_rate)],
    ]
    pending_controls = sum(
        item.etat_controle == "EN_ATTENTE" for item in controls
    )
    cancelled_controls = sum(item.etat_controle == "ANNULE" for item in controls)
    if statuses["ARCHIVE"]:
        summary_rows.insert(5, ["Archivés", statuses["ARCHIVE"]])
    if pending_controls:
        summary_rows.insert(7, ["Contrôles en attente", pending_controls])
    if cancelled_controls:
        summary_rows.insert(8, ["Contrôles annulés", cancelled_controls])
    lines += _markdown_table(["Indicateur", "Résultat"], summary_rows)

    lines += ["", "## Écarts détectés", ""]
    lines += [f"- {item}" for item in anomalies] or ["Aucun écart détecté."]
    if anomaly_tracking:
        anomaly_statuses = Counter(item.statut for item in anomaly_tracking)
        lines += ["", "### Traitement des anomalies", ""]
        anomaly_rows = [
            ["À traiter", anomaly_statuses["NOUVELLE"]],
            ["En cours", anomaly_statuses["EN_COURS"]],
            ["Résolues", anomaly_statuses["RESOLUE"]],
        ]
        if anomaly_statuses["ACQUITTEE"]:
            anomaly_rows.insert(1, ["Acquittées", anomaly_statuses["ACQUITTEE"]])
        if anomaly_statuses["IGNOREE"]:
            anomaly_rows.append(["Ignorées", anomaly_statuses["IGNOREE"]])
        lines += _markdown_table(["État", "Nombre"], anomaly_rows)

    lines += ["", "## Lots à examiner", ""]
    if non_conforming:
        lines += _markdown_table(
            ["Lot", "Produit", "Ligne", "Quantité", "Statut"],
            [
                [
                    lot.id_lot,
                    lot.produit,
                    lot.ligne_production,
                    lot.quantite_produite,
                    LOT_STATUS_LABELS.get(
                        lot.statut, lot.statut.replace("_", " ").title()
                    ),
                ]
                for lot in non_conforming
            ],
        )
    else:
        lines.append("Aucun lot à contrôler ou rejeté.")

    lines += ["", "## Défauts les plus fréquents", ""]
    top_count = int(rules.get("report_top_defects", 5))
    if defect_totals:
        unit = "Occurrences" if mode == "occurrences" else "Nombre"
        lines += _markdown_table(
            ["Type", unit],
            [
                [REPORT_LABELS.get(name, name.replace("_", " ").capitalize()), count]
                for name, count in defect_totals.most_common(top_count)
            ],
        )
    else:
        lines.append("Aucun défaut enregistré.")

    lines += ["", "## Résultats par ligne", ""]
    if by_line:
        rows = []
        for line, line_controls in sorted(by_line.items()):
            inspected = sum(item.quantite_controlee for item in line_controls)
            defects = sum(item.nombre_defauts for item in line_controls)
            rows.append(
                [
                    line,
                    len(line_controls),
                    inspected,
                    _percent(weighted_defect_rate(defects, inspected)),
                ]
            )
        lines += _markdown_table(
            ["Ligne", "Contrôles", "Quantité contrôlée", "Taux pondéré"],
            rows,
        )
    else:
        lines.append("Aucune donnée de contrôle disponible par ligne.")

    thresholds = rules["thresholds"]
    lines += [
        "",
        "## Seuils appliqués",
        "",
    ]
    lines += _markdown_table(
        ["Décision", "Règle"],
        [
            ["Conforme", f"Taux ≤ {_percent(float(thresholds['conforme_max']))}"],
            [
                "À contrôler",
                f"{_percent(float(thresholds['conforme_max']))} < taux ≤ "
                f"{_percent(float(thresholds['a_controler_max']))}",
            ],
            ["Rejeté", f"Taux > {_percent(float(thresholds['a_controler_max']))}"],
            ["Alerte", f"Taux > {_percent(float(thresholds['abnormal_rate']))}"],
        ],
    )
    lines += ["", "## Équipements", ""]
    if equipment:
        equipment_statuses = Counter(item.statut for item in equipment)
        open_issues = [
            issue
            for issue in equipment_issues
            if issue.statut in {"OUVERT", "EN_COURS"}
        ]
        total_usage_minutes = sum(item.duree_minutes for item in equipment_usage)
        equipment_rows = [
            ["Équipements suivis", len(equipment)],
            ["Disponibles", equipment_statuses["DISPONIBLE"]],
            ["Incidents ouverts", len(open_issues)],
            [
                "Utilisation enregistrée",
                f"{total_usage_minutes / 60:.1f}".replace(".", ",") + " h",
            ],
        ]
        for status, label in (
            ("EN_UTILISATION", "En utilisation"),
            ("SURVEILLANCE", "Sous surveillance"),
            ("MAINTENANCE", "En maintenance"),
            ("HORS_SERVICE", "Hors service"),
        ):
            if equipment_statuses[status]:
                equipment_rows.insert(-2, [label, equipment_statuses[status]])
        lines += _markdown_table(["Indicateur", "Résultat"], equipment_rows)
        if open_issues:
            lines += ["", "### Incidents en cours", ""]
            equipment_by_id = {
                item.id_equipement: item for item in equipment
            }
            lines += _markdown_table(
                ["Incident", "Équipement", "Gravité", "Statut", "Description"],
                [
                    [
                        issue.id_incident,
                        (
                            equipment_by_id[issue.id_equipement].nom
                            if issue.id_equipement in equipment_by_id
                            else issue.id_equipement
                        ),
                        REPORT_LABELS.get(issue.gravite, issue.gravite),
                        REPORT_LABELS.get(issue.statut, issue.statut),
                        issue.description,
                    ]
                    for issue in open_issues
                ],
            )
    else:
        lines.append("Aucun équipement enregistré.")
    lines += [
        "",
    ]
    reports = Path(root) / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / f"quality_report_{now:%Y%m%d_%H%M%S}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
