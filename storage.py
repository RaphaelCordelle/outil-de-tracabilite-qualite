"""Lecture et écriture des fichiers locaux de l'application."""

from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import time

from models import (
    ControleQualite,
    Equipement,
    IncidentEquipement,
    Lot,
    QualitySummary,
    SuiviAnomalie,
    UtilisationEquipement,
)

LOT_FIELDS = [
    "id_lot",
    "date_creation",
    "produit",
    "quantite_produite",
    "ligne_production",
    "statut",
    "commentaire",
]
LEGACY_CONTROL_FIELDS = [
    "id_controle",
    "id_lot",
    "date_controle",
    "quantite_controlee",
    "nombre_defauts",
    "type_defaut",
    "taux_defaut",
    "resultat",
    "commentaire",
]
CONTROL_FIELDS = [*LEGACY_CONTROL_FIELDS, "etat_controle"]
EQUIPMENT_FIELDS = [
    "id_equipement",
    "nom",
    "categorie",
    "zone",
    "criticite",
    "statut",
    "description",
    "guide_fichier",
    "commentaire",
]
ISSUE_FIELDS = [
    "id_incident",
    "id_equipement",
    "date_signalement",
    "gravite",
    "categorie",
    "description",
    "statut",
    "action",
    "date_resolution",
]
USAGE_FIELDS = [
    "id_utilisation",
    "id_equipement",
    "debut",
    "fin",
    "utilisateur",
    "motif",
    "duree_minutes",
]
ANOMALY_FIELDS = [
    "id_anomalie",
    "cle_anomalie",
    "source",
    "type_anomalie",
    "entite_type",
    "entite_id",
    "gravite",
    "description",
    "statut",
    "commentaire",
    "date_detection",
    "date_mise_a_jour",
    "date_resolution",
]
LEGACY_AUDIT_FIELDS = [
    "horodatage",
    "evenement",
    "type_entite",
    "id_entite",
    "details",
]
AUDIT_FIELDS = [*LEGACY_AUDIT_FIELDS, "profil"]


class StorageError(RuntimeError):
    """Erreur de lecture ou d'écriture avec un message exploitable."""


def replace_file_with_retry(source: Path, destination: Path) -> None:
    """Tolère les verrouillages Windows très brefs lors d'un remplacement atomique."""

    for attempt in range(5):
        try:
            source.replace(destination)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))


class CsvRepository:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.data_dir = self.root / "data"
        self.reports_dir = self.root / "reports"
        self.exports_dir = self.root / "exports"
        self.config_path = self.root / "config" / "quality_rules.json"
        self.preferences_path = self.data_dir / "preferences.json"
        self.lots_path = self.data_dir / "lots.csv"
        self.controls_path = self.data_dir / "controls.csv"
        self.equipment_path = self.data_dir / "equipment.csv"
        self.equipment_issues_path = self.data_dir / "equipment_issues.csv"
        self.equipment_usage_path = self.data_dir / "equipment_usage.csv"
        self.anomaly_tracking_path = self.data_dir / "anomaly_tracking.csv"
        self.audit_path = self.data_dir / "audit_events.csv"
        first_launch = not self.data_dir.exists()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if first_launch:
            samples = self.root / "samples"
            for source in samples.glob("*.csv"):
                shutil.copy2(source, self.data_dir / source.name)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_csv(self.lots_path, LOT_FIELDS)
        self._ensure_csv(self.controls_path, CONTROL_FIELDS)
        self._ensure_csv(self.equipment_path, EQUIPMENT_FIELDS)
        self._ensure_csv(self.equipment_issues_path, ISSUE_FIELDS)
        self._ensure_csv(self.equipment_usage_path, USAGE_FIELDS)
        self._ensure_csv(self.anomaly_tracking_path, ANOMALY_FIELDS)
        self._ensure_csv(self.audit_path, AUDIT_FIELDS)
        self._migrate_controls_schema()
        self._migrate_audit_schema()

    @staticmethod
    def _ensure_csv(path: Path, fields: list[str]) -> None:
        if not path.exists():
            CsvRepository._write_rows(path, fields, [], keep_backup=False)

    def _migrate_controls_schema(self) -> None:
        """Ajoute l'état de cycle de vie aux fichiers créés par les versions 1.0 à 1.3."""

        try:
            with self.controls_path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames == CONTROL_FIELDS:
                    return
                if reader.fieldnames != LEGACY_CONTROL_FIELDS:
                    return
                rows = list(reader)
            for row in rows:
                row["etat_controle"] = "VALIDE"
            self._write_rows(self.controls_path, CONTROL_FIELDS, rows)
        except (OSError, UnicodeError, csv.Error) as exc:
            raise StorageError(
                f"Migration impossible pour {self.controls_path.name} : {exc}."
            ) from exc

    def _migrate_audit_schema(self) -> None:
        """Ajoute le profil aux événements enregistrés par les anciennes versions."""

        try:
            with self.audit_path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames == AUDIT_FIELDS:
                    return
                if reader.fieldnames != LEGACY_AUDIT_FIELDS:
                    return
                rows = list(reader)
            for row in rows:
                row["profil"] = "SYSTEME"
            self._write_rows(self.audit_path, AUDIT_FIELDS, rows)
        except (OSError, UnicodeError, csv.Error) as exc:
            raise StorageError(
                f"Migration impossible pour {self.audit_path.name} : {exc}."
            ) from exc

    def load_rules(self) -> dict:
        try:
            with self.config_path.open(encoding="utf-8") as stream:
                data = json.load(stream)
        except FileNotFoundError as exc:
            raise StorageError(f"Configuration introuvable : {self.config_path}.") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Configuration JSON illisible : {exc}.") from exc
        if not isinstance(data, dict):
            raise StorageError("La configuration JSON doit contenir un objet.")
        return data

    def save_rules(self, rules: dict) -> None:
        """Enregistre le JSON avec sauvegarde de la configuration précédente."""

        temporary = self.config_path.with_suffix(".json.tmp")
        backup = self.config_path.with_suffix(".json.bak")
        try:
            temporary.write_text(
                json.dumps(rules, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            if self.config_path.exists():
                shutil.copy2(self.config_path, backup)
            replace_file_with_retry(temporary, self.config_path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StorageError(
                f"Écriture impossible dans {self.config_path.name} : {exc}."
            ) from exc

    def load_interface_mode(self, default: str) -> str:
        if not self.preferences_path.exists():
            return default
        try:
            data = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            return str(data.get("interface_mode", default))
        except (OSError, json.JSONDecodeError, AttributeError) as exc:
            raise StorageError(f"Préférences illisibles : {exc}.") from exc

    def save_interface_mode(self, mode: str) -> None:
        try:
            self.preferences_path.write_text(
                json.dumps({"interface_mode": mode}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise StorageError(f"Enregistrement des préférences impossible : {exc}.") from exc

    @staticmethod
    def _read_rows(path: Path, expected_fields: list[str]) -> list[dict[str, str]]:
        try:
            with path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames != expected_fields:
                    actual = ", ".join(reader.fieldnames or []) or "aucun en-tête"
                    raise StorageError(
                        f"En-tête invalide dans {path.name} ({actual}). "
                        f"Attendu : {', '.join(expected_fields)}."
                    )
                rows = list(reader)
                if any(None in row for row in rows):
                    raise StorageError(f"Une ligne de {path.name} contient trop de colonnes.")
                return rows
        except StorageError:
            raise
        except (OSError, UnicodeError, csv.Error) as exc:
            raise StorageError(f"Fichier {path.name} illisible ou corrompu : {exc}.") from exc

    def load_lots(self) -> list[Lot]:
        lots: list[Lot] = []
        for line, row in enumerate(self._read_rows(self.lots_path, LOT_FIELDS), start=2):
            try:
                lots.append(Lot(**{**row, "quantite_produite": int(row["quantite_produite"])}))
            except (TypeError, ValueError) as exc:
                raise StorageError(
                    f"Valeur invalide dans lots.csv à la ligne {line}: {exc}."
                ) from exc
        return lots

    def load_controls(self) -> list[ControleQualite]:
        controls: list[ControleQualite] = []
        for line, row in enumerate(self._read_rows(self.controls_path, CONTROL_FIELDS), start=2):
            try:
                controls.append(
                    ControleQualite(
                        **{
                            **row,
                            "quantite_controlee": int(row["quantite_controlee"]),
                            "nombre_defauts": int(row["nombre_defauts"]),
                            "taux_defaut": float(row["taux_defaut"]),
                        }
                    )
                )
            except (TypeError, ValueError) as exc:
                raise StorageError(
                    f"Valeur invalide dans controls.csv à la ligne {line}: {exc}."
                ) from exc
        return controls

    def load_equipment(self) -> list[Equipement]:
        equipment: list[Equipement] = []
        for line, row in enumerate(
            self._read_rows(self.equipment_path, EQUIPMENT_FIELDS), start=2
        ):
            try:
                equipment.append(Equipement(**row))
            except TypeError as exc:
                raise StorageError(
                    f"Valeur invalide dans equipment.csv à la ligne {line}: {exc}."
                ) from exc
        return equipment

    def load_equipment_issues(self) -> list[IncidentEquipement]:
        issues: list[IncidentEquipement] = []
        for line, row in enumerate(
            self._read_rows(self.equipment_issues_path, ISSUE_FIELDS), start=2
        ):
            try:
                issues.append(IncidentEquipement(**row))
            except TypeError as exc:
                raise StorageError(
                    f"Valeur invalide dans equipment_issues.csv à la ligne {line}: {exc}."
                ) from exc
        return issues

    def load_equipment_usage(self) -> list[UtilisationEquipement]:
        usage: list[UtilisationEquipement] = []
        for line, row in enumerate(
            self._read_rows(self.equipment_usage_path, USAGE_FIELDS), start=2
        ):
            try:
                usage.append(
                    UtilisationEquipement(
                        **{**row, "duree_minutes": int(row["duree_minutes"])}
                    )
                )
            except (TypeError, ValueError) as exc:
                raise StorageError(
                    f"Valeur invalide dans equipment_usage.csv à la ligne {line}: {exc}."
                ) from exc
        return usage

    def load_anomaly_tracking(self) -> list[SuiviAnomalie]:
        tracking: list[SuiviAnomalie] = []
        for line, row in enumerate(
            self._read_rows(self.anomaly_tracking_path, ANOMALY_FIELDS), start=2
        ):
            try:
                tracking.append(SuiviAnomalie(**row))
            except TypeError as exc:
                raise StorageError(
                    f"Valeur invalide dans anomaly_tracking.csv à la ligne {line}: {exc}."
                ) from exc
        return tracking

    def load_audit_events(self, limit: int | None = None) -> list[dict[str, str]]:
        rows = self._read_rows(self.audit_path, AUDIT_FIELDS)
        return rows[-limit:] if limit is not None else rows

    @staticmethod
    def _write_rows(
        path: Path, fields: list[str], rows: list[dict], *, keep_backup: bool = True
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        backup = path.with_suffix(path.suffix + ".bak")
        try:
            with temporary.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
                writer.writeheader()
                writer.writerows(rows)
                stream.flush()
            if keep_backup and path.exists():
                shutil.copy2(path, backup)
            replace_file_with_retry(temporary, path)
        except (OSError, csv.Error, ValueError) as exc:
            temporary.unlink(missing_ok=True)
            raise StorageError(f"Écriture impossible dans {path.name} : {exc}.") from exc

    def save_lots(self, lots: list[Lot]) -> None:
        self._write_rows(self.lots_path, LOT_FIELDS, [lot.to_dict() for lot in lots])

    def save_controls(self, controls: list[ControleQualite]) -> None:
        self._write_rows(
            self.controls_path, CONTROL_FIELDS, [control.to_dict() for control in controls]
        )

    def save_equipment(self, equipment: list[Equipement]) -> None:
        self._write_rows(
            self.equipment_path,
            EQUIPMENT_FIELDS,
            [item.to_dict() for item in equipment],
        )

    def save_equipment_issues(self, issues: list[IncidentEquipement]) -> None:
        self._write_rows(
            self.equipment_issues_path,
            ISSUE_FIELDS,
            [item.to_dict() for item in issues],
        )

    def save_equipment_usage(self, usage: list[UtilisationEquipement]) -> None:
        self._write_rows(
            self.equipment_usage_path,
            USAGE_FIELDS,
            [item.to_dict() for item in usage],
        )

    def save_anomaly_tracking(self, tracking: list[SuiviAnomalie]) -> None:
        self._write_rows(
            self.anomaly_tracking_path,
            ANOMALY_FIELDS,
            [item.to_dict() for item in tracking],
        )

    def record_event(
        self,
        event: str,
        entity_type: str,
        entity_id: str,
        details: str = "",
        profile: str = "SYSTEME",
    ) -> None:
        """Ajoute un événement métier sans enregistrer de donnée sensible."""

        row = {
            "horodatage": datetime.now().astimezone().isoformat(timespec="seconds"),
            "evenement": event,
            "type_entite": entity_type,
            "id_entite": entity_id,
            "details": details[:500],
            "profil": profile,
        }
        try:
            with self.audit_path.open("a", newline="", encoding="utf-8") as stream:
                csv.DictWriter(stream, fieldnames=AUDIT_FIELDS).writerow(row)
        except (OSError, csv.Error) as exc:
            raise StorageError(f"Journal d'audit inaccessible : {exc}.") from exc

    def restore_sample_data(self) -> None:
        """Restaure le jeu fictif livré, après confirmation dans l'appelant."""

        samples = self.root / "samples"
        required = {"lots.csv", "controls.csv", "audit_events.csv"}
        for name in (
            "lots.csv",
            "controls.csv",
            "equipment.csv",
            "equipment_issues.csv",
            "equipment_usage.csv",
            "anomaly_tracking.csv",
            "audit_events.csv",
        ):
            source = samples / name
            destination = self.data_dir / name
            if not source.exists():
                if name in required:
                    raise StorageError(f"Fichier d'exemple introuvable : {source}.")
                continue
            if destination.exists():
                shutil.copy2(destination, destination.with_suffix(".csv.bak"))
            shutil.copy2(source, destination)

    def export(
        self,
        lots: list[Lot],
        controls: list[ControleQualite],
        summary: QualitySummary,
        equipment: list[Equipement] | None = None,
        issues: list[IncidentEquipement] | None = None,
        usage: list[UtilisationEquipement] | None = None,
        anomaly_tracking: list[SuiviAnomalie] | None = None,
    ) -> Path:
        """Crée un export horodaté et un manifeste SHA-256 de contrôle d'intégrité."""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        destination = self.exports_dir / f"export_{timestamp}"
        destination.mkdir(parents=True, exist_ok=False)
        self._write_rows(
            destination / "lots_export.csv",
            LOT_FIELDS,
            [lot.to_dict() for lot in lots],
            keep_backup=False,
        )
        self._write_rows(
            destination / "controls_export.csv",
            CONTROL_FIELDS,
            [control.to_dict() for control in controls],
            keep_backup=False,
        )
        self._write_rows(
            destination / "equipment_export.csv",
            EQUIPMENT_FIELDS,
            [item.to_dict() for item in equipment or []],
            keep_backup=False,
        )
        self._write_rows(
            destination / "equipment_issues_export.csv",
            ISSUE_FIELDS,
            [item.to_dict() for item in issues or []],
            keep_backup=False,
        )
        self._write_rows(
            destination / "equipment_usage_export.csv",
            USAGE_FIELDS,
            [item.to_dict() for item in usage or []],
            keep_backup=False,
        )
        self._write_rows(
            destination / "anomaly_tracking_export.csv",
            ANOMALY_FIELDS,
            [item.to_dict() for item in anomaly_tracking or []],
            keep_backup=False,
        )
        shutil.copy2(self.config_path, destination / "quality_rules_export.json")
        shutil.copy2(self.audit_path, destination / "audit_events_export.csv")
        summary_path = destination / "quality_summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    **asdict(summary),
                    "total_equipements": len(equipment or []),
                    "incidents_equipements_ouverts": sum(
                        item.statut in {"OUVERT", "EN_COURS"}
                        for item in issues or []
                    ),
                    "duree_utilisation_equipements_minutes": sum(
                        item.duree_minutes for item in usage or []
                    ),
                    "anomalies_actives": sum(
                        item.statut
                        in {"NOUVELLE", "ACQUITTEE", "EN_COURS"}
                        for item in anomaly_tracking or []
                    ),
                    "date_export": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "disclaimer": "Données et procédures intégralement fictives.",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        files = sorted(path for path in destination.iterdir() if path.is_file())
        manifest = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
        (destination / "manifest_sha256.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        return destination
