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

DISCLAIMER = (
    "Données fictives utilisées uniquement pour présenter le projet."
)


def _markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
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
        "# Rapport qualité",
        "",
        f"Date : {now:%d/%m/%Y à %H:%M}",
        "",
        f"_Note : {DISCLAIMER}_",
        "",
        "## Situation générale",
        "",
    ]
    lines += _markdown_table(
        ["Indicateur", "Valeur"],
        [
            ["Total des lots", len(lots)],
            ["Lots conformes", statuses["CONFORME"]],
            ["Lots à contrôler", statuses["A_CONTROLER"]],
            ["Lots rejetés", statuses["REJETE"]],
            ["Lots sans contrôle", statuses["SANS_CONTROLE"]],
            ["Lots archivés", statuses["ARCHIVE"]],
            ["Contrôles validés", len(validated_controls)],
            ["Contrôles en attente", sum(
                item.etat_controle == "EN_ATTENTE" for item in controls
            )],
            ["Contrôles annulés", sum(
                item.etat_controle == "ANNULE" for item in controls
            )],
            ["Quantité totale contrôlée", total_inspected],
            ["Défauts comptabilisés", total_defects],
            ["Couverture des lots actifs", f"{coverage:.1f} %"],
            ["Taux de défaut moyen pondéré", f"{weighted_rate:.2f} %"],
        ],
    )

    lines += ["", "## Écarts détectés", ""]
    lines += [f"- {item}" for item in anomalies] or ["Aucun écart détecté."]
    if anomaly_tracking:
        anomaly_statuses = Counter(item.statut for item in anomaly_tracking)
        lines += ["", "### Suivi des anomalies", ""]
        lines += _markdown_table(
            ["Statut", "Nombre"],
            [
                ["Nouvelles", anomaly_statuses["NOUVELLE"]],
                ["Acquittées", anomaly_statuses["ACQUITTEE"]],
                ["En cours", anomaly_statuses["EN_COURS"]],
                ["Ignorées avec justification", anomaly_statuses["IGNOREE"]],
                ["Résolues", anomaly_statuses["RESOLUE"]],
            ],
        )

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
                    lot.statut.replace("_", " ").title(),
                ]
                for lot in non_conforming
            ],
        )
    else:
        lines.append("Aucun lot à contrôler ou rejeté.")

    lines += ["", "## Défauts les plus fréquents", ""]
    top_count = int(rules.get("report_top_defects", 5))
    if defect_totals:
        unit = "occurrence(s)" if mode == "occurrences" else "défaut(s)"
        lines += _markdown_table(
            ["Type de défaut", unit],
            [[name, count] for name, count in defect_totals.most_common(top_count)],
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
                    f"{weighted_defect_rate(defects, inspected):.2f} %",
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
            ["Conforme", f"Taux ≤ {float(thresholds['conforme_max']):.2f} %"],
            [
                "À contrôler",
                f"{float(thresholds['conforme_max']):.2f} % < taux ≤ "
                f"{float(thresholds['a_controler_max']):.2f} %",
            ],
            ["Rejeté", f"Taux > {float(thresholds['a_controler_max']):.2f} %"],
            ["Alerte", f"Taux > {float(thresholds['abnormal_rate']):.2f} %"],
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
        lines += _markdown_table(
            ["Indicateur équipement", "Valeur"],
            [
                ["Équipements suivis", len(equipment)],
                ["Disponibles", equipment_statuses["DISPONIBLE"]],
                ["En utilisation", equipment_statuses["EN_UTILISATION"]],
                ["Sous surveillance", equipment_statuses["SURVEILLANCE"]],
                ["En maintenance", equipment_statuses["MAINTENANCE"]],
                ["Hors service", equipment_statuses["HORS_SERVICE"]],
                ["Incidents ouverts", len(open_issues)],
                [
                    "Temps d'utilisation enregistré",
                    f"{total_usage_minutes / 60:.1f} h",
                ],
            ],
        )
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
                        issue.gravite,
                        issue.statut,
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
