"""Tests du suivi des équipements, incidents et utilisations."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from models import Equipement, IncidentEquipement
from quality_rules import ValidationError
from reporting import generate_report
from services import TraceabilityService
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
