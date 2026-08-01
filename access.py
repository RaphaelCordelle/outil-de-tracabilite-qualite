"""Profils d'affichage et droits associés dans l'interface."""

from __future__ import annotations


MODE_LABELS = {
    "EMPLOYE": "Employé",
    "QUALITE": "Inspecteur qualité",
    "MANAGER": "Manager",
}
MODE_DESCRIPTIONS = {
    "EMPLOYE": "Saisie des lots, contrôles et incidents",
    "QUALITE": "Validation des contrôles et traitement des anomalies",
    "MANAGER": "Suivi global, configuration et exports",
}

MODE_PERMISSIONS = {
    "EMPLOYE": {
        "create_lot",
        "edit_lot",
        "add_control",
        "edit_pending_control",
        "report_issue",
        "use_equipment",
    },
    "QUALITE": {
        "create_lot",
        "edit_lot",
        "add_control",
        "validate_controls",
        "archive_lot",
        "manage_anomalies",
        "report_issue",
        "manage_incidents",
        "generate_report",
    },
    "MANAGER": {
        "create_lot",
        "edit_lot",
        "add_control",
        "validate_controls",
        "archive_lot",
        "manage_anomalies",
        "manage_equipment",
        "report_issue",
        "manage_incidents",
        "use_equipment",
        "generate_report",
        "export_data",
        "view_audit",
        "configure_rules",
    },
}


def has_permission(mode: str, permission: str) -> bool:
    return permission in MODE_PERMISSIONS.get(mode, set())
