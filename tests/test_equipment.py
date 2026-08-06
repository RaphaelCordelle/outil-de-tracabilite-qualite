"""Tests du suivi des équipements, incidents et utilisations."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from models import Equipement, IncidentEquipement
from quality_rules import ValidationError
from reporting import generate_report
from services import TraceabilityService
from storage import StorageError
from test_requirements import RULES


class EquipmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "config").mkdir()
        (self.root / "config" / "quality_rules.json").write_text(
            json.dumps(RULES), encoding="utf-8"
        )
        self.service = TraceabilityService(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def equipment(identifier: str = "EQ-TST-001") -> Equipement:
        return Equipement(
            id_equipement=identifier,
            nom="Équipement de contrôle",
            categorie="PROCESS",
            zone="Atelier",
            criticite="HAUTE",
            statut="DISPONIBLE",
            description="Équipement générique utilisé par les tests.",
        )

    def issue(
        self, equipment_id: str, severity: str = "MAJEURE"
    ) -> IncidentEquipement:
        return IncidentEquipement(
            id_incident=self.service.next_issue_id(),
            id_equipement=equipment_id,
            date_signalement=datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            gravite=severity,
            categorie="FONCTIONNEMENT",
            description="Comportement inhabituel constaté.",
        )

    def test_equipment_creation_is_persisted(self) -> None:
        created = self.service.create_equipment(self.equipment())
        reloaded = TraceabilityService(self.root)
        self.assertEqual(
            reloaded.require_equipment(created.id_equipement).nom,
            "Équipement de contrôle",
        )

    def test_issue_and_equipment_are_restored_after_write_failure(self) -> None:
        equipment = self.service.create_equipment(self.equipment())
        issue = self.issue(equipment.id_equipement)
        repository = self.service.repository
        original_write = repository._write_rows

        def fail_on_equipment(path, fields, rows, *, keep_backup=True):
            if path == repository.equipment_path:
                raise StorageError("Panne simulée sur equipment.csv")
            return original_write(
                path, fields, rows, keep_backup=keep_backup
            )

        with patch.object(
            repository, "_write_rows", side_effect=fail_on_equipment
        ):
            with self.assertRaisesRegex(StorageError, "Panne simulée"):
                self.service.report_equipment_issue(issue)

        self.assertEqual(self.service.equipment_issues, [])
        self.assertEqual(equipment.statut, "DISPONIBLE")
        reloaded = TraceabilityService(self.root)
        self.assertEqual(reloaded.equipment_issues, [])
        self.assertEqual(
            reloaded.require_equipment(equipment.id_equipement).statut,
            "DISPONIBLE",
        )

    def test_usage_records_start_end_user_and_duration(self) -> None:
        equipment = self.service.create_equipment(self.equipment())
        start = datetime(2026, 7, 30, 8, 15, tzinfo=timezone.utc)
        usage = self.service.start_equipment_usage(
            equipment.id_equipement, "op-01", "Série courte", start
        )
        self.assertEqual(equipment.statut, "EN_UTILISATION")
        self.assertEqual(usage.utilisateur, "OP-01")
        with self.assertRaisesRegex(ValidationError, "déjà en cours"):
            self.service.start_equipment_usage(
                equipment.id_equipement, "OP-02", "Autre série", start
            )
        ended = self.service.end_equipment_usage(
            equipment.id_equipement, start + timedelta(minutes=42)
        )
        self.assertEqual(ended.duree_minutes, 42)
        self.assertEqual(equipment.statut, "DISPONIBLE")

    def test_critical_issue_blocks_usage_until_resolution(self) -> None:
        equipment = self.service.create_equipment(self.equipment())
        issue = self.service.report_equipment_issue(
            self.issue(equipment.id_equipement, "CRITIQUE")
        )
        self.assertEqual(equipment.statut, "HORS_SERVICE")
        with self.assertRaisesRegex(ValidationError, "hors service"):
            self.service.start_equipment_usage(
                equipment.id_equipement, "OP-01", "Essai"
            )
        self.service.update_equipment_issue(
            issue.id_incident,
            statut="RESOLU",
            action="Vérification réalisée et remise en service autorisée.",
        )
        self.assertEqual(equipment.statut, "DISPONIBLE")

    def test_last_resolved_major_issue_releases_equipment(self) -> None:
        equipment = self.service.create_equipment(self.equipment())
        issue = self.service.report_equipment_issue(
            self.issue(equipment.id_equipement, "MAJEURE")
        )
        self.assertEqual(equipment.statut, "SURVEILLANCE")

        self.service.update_equipment_issue(
            issue.id_incident,
            statut="EN_COURS",
            action="Réglage en cours.",
        )
        self.service.update_equipment_issue(
            issue.id_incident,
            statut="RESOLU",
            action="Réglage contrôlé, fonctionnement normal.",
        )

        self.assertEqual(equipment.statut, "DISPONIBLE")
        self.assertEqual(self.service.open_equipment_issues(), [])
        reloaded = TraceabilityService(self.root)
        self.assertEqual(
            reloaded.require_equipment(equipment.id_equipement).statut,
            "DISPONIBLE",
        )

    def test_manual_maintenance_is_not_cancelled_by_a_minor_issue(self) -> None:
        equipment = self.service.create_equipment(self.equipment())
        self.service.update_equipment(equipment.id_equipement, statut="MAINTENANCE")
        self.service.report_equipment_issue(
            self.issue(equipment.id_equipement, "MINEURE")
        )
        self.assertEqual(equipment.statut, "MAINTENANCE")

    def test_incident_statuses_follow_a_simple_sequence(self) -> None:
        equipment = self.service.create_equipment(self.equipment())
        issue = self.service.report_equipment_issue(self.issue(equipment.id_equipement))
        with self.assertRaisesRegex(ValidationError, "Passage impossible"):
            self.service.update_equipment_issue(
                issue.id_incident, statut="CLOTURE", action="Clôture directe"
            )
        self.service.update_equipment_issue(
            issue.id_incident, statut="EN_COURS", action="Diagnostic lancé"
        )
        self.service.update_equipment_issue(
            issue.id_incident, statut="RESOLU", action="Réglage vérifié"
        )
        self.service.update_equipment_issue(
            issue.id_incident, statut="CLOTURE", action="Suivi terminé"
        )
        self.assertEqual(issue.statut, "CLOTURE")

    def test_guide_is_optional_and_restricted_to_local_guide_folder(self) -> None:
        equipment = self.equipment()
        self.service.create_equipment(equipment)
        self.assertIsNone(
            self.service.equipment_guide_path(equipment.id_equipement)
        )
        guide = self.root / "docs" / "equipment-guides" / "guide.md"
        guide.parent.mkdir(parents=True)
        guide.write_text("# Guide", encoding="utf-8")
        self.service.update_equipment(
            equipment.id_equipement,
            guide_fichier="docs/equipment-guides/guide.md",
        )
        self.assertEqual(
            self.service.equipment_guide_path(equipment.id_equipement), guide
        )

    def test_report_and_export_include_equipment_tracking(self) -> None:
        equipment = self.service.create_equipment(self.equipment())
        self.service.report_equipment_issue(self.issue(equipment.id_equipement))
        report = generate_report(
            self.root,
            self.service.lots,
            self.service.controls,
            self.service.rules,
            self.service.equipment,
            self.service.equipment_issues,
            self.service.equipment_usage,
        )
        self.assertIn(
            "## Équipements", report.read_text(encoding="utf-8")
        )
        exported = self.service.repository.export(
            self.service.lots,
            self.service.controls,
            self.service.summary(),
            self.service.equipment,
            self.service.equipment_issues,
            self.service.equipment_usage,
        )
        self.assertTrue((exported / "equipment_export.csv").exists())
        self.assertTrue((exported / "equipment_issues_export.csv").exists())
        self.assertTrue((exported / "equipment_usage_export.csv").exists())


if __name__ == "__main__":
    unittest.main()
