"""Persistance CSV, journal d'audit et exports locaux.

Les écritures passent par un fichier temporaire puis un remplacement atomique.
Une sauvegarde ``.bak`` de la version précédente est conservée pour faciliter
la récupération après une erreur de manipulation.
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil

from models import ControleQualite, Lot, QualitySummary

LOT_FIELDS = [
    "id_lot",
    "date_creation",
    "produit",
    "quantite_produite",
    "ligne_production",
    "statut",
    "commentaire",
]
CONTROL_FIELDS = [
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
AUDIT_FIELDS = ["horodatage", "evenement", "type_entite", "id_entite", "details"]


class StorageError(RuntimeError):
    """Erreur de lecture ou d'écriture avec un message exploitable."""


class CsvRepository:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.data_dir = self.root / "data"
        self.config_path = self.root / "config" / "quality_rules.json"
        self.lots_path = self.data_dir / "lots.csv"
        self.controls_path = self.data_dir / "controls.csv"
        self.audit_path = self.data_dir / "audit_events.csv"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_csv(self.lots_path, LOT_FIELDS)
        self._ensure_csv(self.controls_path, CONTROL_FIELDS)
        self._ensure_csv(self.audit_path, AUDIT_FIELDS)

    @staticmethod
    def _ensure_csv(path: Path, fields: list[str]) -> None:
        if not path.exists():
            CsvRepository._write_rows(path, fields, [], keep_backup=False)

    def load_rules(self) -> dict:
        try:
            with self.config_path.open(encoding="utf-8") as stream:
                data = json.load(stream)
        except FileNotFoundError as exc:
            raise StorageError(
                f"Configuration introuvable : {self.config_path}."
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Configuration JSON illisible : {exc}.") from exc
        if not isinstance(data, dict):
            raise StorageError("La configuration JSON doit contenir un objet.")
        return data

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
                lots.append(
                    Lot(**{**row, "quantite_produite": int(row["quantite_produite"])})
                )
            except (TypeError, ValueError) as exc:
                raise StorageError(
                    f"Valeur invalide dans lots.csv à la ligne {line}: {exc}."
                ) from exc
        return lots

    def load_controls(self) -> list[ControleQualite]:
        controls: list[ControleQualite] = []
        for line, row in enumerate(
            self._read_rows(self.controls_path, CONTROL_FIELDS), start=2
        ):
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

    def load_audit_events(self, limit: int | None = None) -> list[dict[str, str]]:
        rows = self._read_rows(self.audit_path, AUDIT_FIELDS)
        return rows[-limit:] if limit is not None else rows

    @staticmethod
    def _write_rows(
        path: Path,
        fields: list[str],
        rows: list[dict],
        *,
        keep_backup: bool = True,
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
            temporary.replace(path)
        except (OSError, csv.Error, ValueError) as exc:
            temporary.unlink(missing_ok=True)
            raise StorageError(f"Écriture impossible dans {path.name} : {exc}.") from exc

    def save_lots(self, lots: list[Lot]) -> None:
        self._write_rows(self.lots_path, LOT_FIELDS, [lot.to_dict() for lot in lots])

    def save_controls(self, controls: list[ControleQualite]) -> None:
        self._write_rows(
            self.controls_path,
            CONTROL_FIELDS,
            [control.to_dict() for control in controls],
        )

    def record_event(
        self, event: str, entity_type: str, entity_id: str, details: str = ""
    ) -> None:
        """Ajoute un événement métier sans enregistrer de donnée sensible."""

        row = {
            "horodatage": datetime.now().astimezone().isoformat(timespec="seconds"),
            "evenement": event,
            "type_entite": entity_type,
            "id_entite": entity_id,
            "details": details[:500],
        }
        try:
            with self.audit_path.open("a", newline="", encoding="utf-8") as stream:
                csv.DictWriter(stream, fieldnames=AUDIT_FIELDS).writerow(row)
        except (OSError, csv.Error) as exc:
            raise StorageError(f"Journal d'audit inaccessible : {exc}.") from exc

    def restore_sample_data(self) -> None:
        """Restaure le jeu fictif livré après confirmation dans l'interface."""

        samples = self.root / "samples"
        for name in ("lots.csv", "controls.csv", "audit_events.csv"):
            source = samples / name
            destination = self.data_dir / name
            if not source.exists():
                raise StorageError(f"Fichier d'exemple introuvable : {source}.")
            if destination.exists():
                shutil.copy2(destination, destination.with_suffix(".csv.bak"))
            shutil.copy2(source, destination)

    def export(
        self,
        lots: list[Lot],
        controls: list[ControleQualite],
        summary: QualitySummary,
    ) -> Path:
        """Crée un export horodaté et un manifeste de contrôle."""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        destination = self.root / "exports" / f"export_{timestamp}"
        destination.mkdir(parents=True, exist_ok=False)
        lots_path = destination / "lots_export.csv"
        controls_path = destination / "controls_export.csv"
        self._write_rows(
            lots_path, LOT_FIELDS, [lot.to_dict() for lot in lots], keep_backup=False
        )
        self._write_rows(
            controls_path,
            CONTROL_FIELDS,
            [control.to_dict() for control in controls],
            keep_backup=False,
        )
        shutil.copy2(self.config_path, destination / "quality_rules_export.json")
        shutil.copy2(self.audit_path, destination / "audit_events_export.csv")
        summary_path = destination / "quality_summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    **asdict(summary),
                    "date_export": datetime.now().astimezone().isoformat(
                        timespec="seconds"
                    ),
                    "disclaimer": "Données et procédures intégralement fictives.",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        files = sorted(path for path in destination.iterdir() if path.is_file())
        manifest = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files
        }
        (destination / "manifest_sha256.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        return destination
