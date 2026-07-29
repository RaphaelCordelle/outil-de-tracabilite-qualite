"""Génération du rapport qualité Markdown."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from models import ControleQualite, Lot
from quality_rules import weighted_defect_rate
from validation import detect_anomalies

DISCLAIMER = (
    "Prototype personnel inspiré d’un environnement de production électronique. "
    "Toutes les données et procédures sont fictives."
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
) -> Path:
    """Produit une synthèse autonome et horodatée, sans modifier les données."""

    now = datetime.now().astimezone()
    total_inspected = sum(item.quantite_controlee for item in controls)
    total_defects = sum(item.nombre_defauts for item in controls)
    weighted_rate = weighted_defect_rate(total_defects, total_inspected)
    statuses = Counter(lot.statut for lot in lots)
    anomalies = detect_anomalies(lots, controls, rules)
    non_archived = [lot for lot in lots if lot.statut != "ARCHIVE"]
    controlled_ids = {control.id_lot for control in controls}
    coverage = (
        round(sum(lot.id_lot in controlled_ids for lot in non_archived) / len(non_archived) * 100, 1)
        if non_archived
        else 0.0
    )
    non_conforming = [
        lot for lot in lots if lot.statut in {"A_CONTROLER", "REJETE"}
    ]

    defect_totals: Counter[str] = Counter()
    mode = rules.get("frequent_defects_mode", "total_defects")
    for item in controls:
        defect_totals[item.type_defaut] += (
            1 if mode == "occurrences" else item.nombre_defauts
        )

    by_line: dict[str, list[ControleQualite]] = {}
    lots_by_id = {lot.id_lot: lot for lot in lots}
    for control in controls:
        lot = lots_by_id.get(control.id_lot)
        if lot:
            by_line.setdefault(lot.ligne_production, []).append(control)

    lines = [
        "# Rapport qualité — Quality Traceability Tool",
        "",
        f"**Généré le :** {now:%Y-%m-%d à %H:%M:%S UTC%z}",
        "",
        f"> {DISCLAIMER}",
        "",
        "## Synthèse exécutive",
        "",
        (
            f"Le jeu analysé contient **{len(lots)} lots** et **{len(controls)} contrôles**. "
            f"La couverture de contrôle atteint **{coverage:.1f} %** et le taux de défaut "
            f"pondéré est de **{weighted_rate:.2f} %**."
        ),
        "",
        "## Indicateurs globaux",
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
            ["Contrôles enregistrés", len(controls)],
            ["Quantité totale contrôlée", total_inspected],
            ["Défauts comptabilisés", total_defects],
            ["Couverture des lots actifs", f"{coverage:.1f} %"],
            ["Taux de défaut moyen pondéré", f"{weighted_rate:.2f} %"],
        ],
    )

    lines += ["", "## Anomalies et alertes", ""]
    lines += [f"- {item}" for item in anomalies] or ["Aucune anomalie détectée."]

    lines += ["", "## Lots nécessitant une attention", ""]
    if non_conforming:
        lines += _markdown_table(
            ["Lot", "Produit", "Ligne", "Quantité", "Statut"],
            [
                [
                    lot.id_lot,
                    lot.produit,
                    lot.ligne_production,
                    lot.quantite_produite,
                    lot.statut,
                ]
                for lot in non_conforming
            ],
        )
    else:
        lines.append("Aucun lot à contrôler ou rejeté.")

    lines += ["", "## Défauts fréquents", ""]
    top_count = int(rules.get("report_top_defects", 5))
    if defect_totals:
        unit = "occurrence(s)" if mode == "occurrences" else "défaut(s)"
        lines += _markdown_table(
            ["Type de défaut", unit],
            [[name, count] for name, count in defect_totals.most_common(top_count)],
        )
    else:
        lines.append("Aucun défaut enregistré.")

    lines += ["", "## Indicateurs par ligne fictive", ""]
    if by_line:
        rows = []
        for line, line_controls in sorted(by_line.items()):
            inspected = sum(item.quantite_controlee for item in line_controls)
            defects = sum(item.nombre_defauts for item in line_controls)
            rows.append(
                [line, len(line_controls), inspected, f"{weighted_defect_rate(defects, inspected):.2f} %"]
            )
        lines += _markdown_table(
            ["Ligne", "Contrôles", "Quantité contrôlée", "Taux pondéré"], rows
        )
    else:
        lines.append("Aucune donnée de contrôle disponible par ligne.")

    thresholds = rules["thresholds"]
    lines += [
        "",
        "## Règles actives",
        "",
        f"- Conforme : taux ≤ {float(thresholds['conforme_max']):.2f} %",
        (
            f"- À contrôler : {float(thresholds['conforme_max']):.2f} % < taux "
            f"≤ {float(thresholds['a_controler_max']):.2f} %"
        ),
        f"- Rejeté : taux > {float(thresholds['a_controler_max']):.2f} %",
        f"- Alerte taux anormal : taux > {float(thresholds['abnormal_rate']):.2f} %",
        "",
        "## Conclusion et limites",
        "",
        (
            "Cette synthèse illustre la consolidation de règles configurables sur un "
            "échantillon fictif. Elle ne constitue ni une décision industrielle réelle, "
            "ni une procédure de libération produit. Le stockage CSV est destiné à un "
            "prototype local mono-utilisateur."
        ),
        "",
    ]
    reports = Path(root) / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / f"quality_report_{now:%Y%m%d_%H%M%S}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
