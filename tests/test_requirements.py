"""Tests fonctionnels reliés aux exigences T-001 à T-016."""

from contextlib import redirect_stdout
from datetime import date
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from console_ui import ConsoleApplication
from models import ControleQualite, Lot
from quality_rules import ValidationError, calculate_defect_rate, determine_result
from reporting import generate_report
from services import TraceabilityService


RULES = {
    "thresholds": {
        "conforme_max": 2,
        "a_controler_max": 5,
        "abnormal_rate": 20,
    },
    "production_lines": ["LINE-01", "LINE-02"],
    "defect_types": ["DEFAUT_VISUEL", "TEST_ELECTRIQUE"],
    "frequent_defects_mode": "total_defects",
    "max_comment_length": 250,
    "report_top_defects": 5,
}


class RequirementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "config").mkdir()
        (self.root / "config" / "quality_rules.json").write_text(
            json.dumps(RULES), encoding="utf-8"
        )
        self.service = TraceabilityService(self.root)
        self.day = date.today()
        self.day_iso = self.day.isoformat()
        self.day_code = self.day.strftime("%Y%m%d")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def lot(self, suffix: int = 1, quantity: int = 500) -> Lot:
        return Lot(
            f"LOT-{self.day_code}-{suffix:03d}",
            self.day_iso,
            "PCB_TEST_A1",
            quantity,
            "LINE-01",
        )

    def control(
        self,
        lot_id: str,
        suffix: int = 1,
        inspected: int = 100,
        defects: int = 3,
    ) -> ControleQualite:
        return ControleQualite(
            f"QC-{self.day_code}-{suffix:03d}",
            lot_id,
            self.day_iso,
            inspected,
            defects,
            "DEFAUT_VISUEL",
            0.0,
            "",
        )

    def test_t001_create_valid_lot(self) -> None:
        created = self.service.create_lot(self.lot())
        self.assertIs(self.service.get_lot(created.id_lot), created)
        self.assertEqual(created.statut, "SANS_CONTROLE")

    def test_t002_duplicate_lot_is_rejected(self) -> None:
        lot = self.service.create_lot(self.lot())
        with self.assertRaisesRegex(ValidationError, "existe déjà"):
            self.service.create_lot(self.lot())
        self.assertEqual(self.service.lots, [lot])

    def test_t003_required_and_invalid_fields_are_rejected(self) -> None:
        invalid = self.lot()
        invalid.produit = ""
        with self.assertRaises(ValidationError):
            self.service.create_lot(invalid)
        invalid = self.lot()
        invalid.quantite_produite = 0
        with self.assertRaises(ValidationError):
            self.service.create_lot(invalid)

    def test_t004_update_is_persisted_and_preserves_control_integrity(self) -> None:
        lot = self.service.create_lot(self.lot())
        self.service.add_control(self.control(lot.id_lot, inspected=100))
        updated = self.service.update_lot(lot.id_lot, commentaire="Revue effectuée")
        self.assertEqual(updated.commentaire, "Revue effectuée")
        reloaded = TraceabilityService(self.root)
        self.assertEqual(reloaded.require_lot(lot.id_lot).commentaire, "Revue effectuée")
        with self.assertRaises(ValidationError):
            self.service.update_lot(lot.id_lot, quantite_produite=50)
        self.assertEqual(lot.quantite_produite, 500)

    def test_t005_search_and_listing_data(self) -> None:
        first = self.service.create_lot(self.lot(1))
        second = self.lot(2)
        second.produit = "MODULE_IO_B2"
        second.ligne_production = "LINE-02"
        self.service.create_lot(second)
        self.assertEqual(self.service.search_lots(first.id_lot, "id"), [first])
        self.assertEqual(self.service.search_lots("module", "produit"), [second])
        self.assertEqual(len(self.service.search_lots("LINE", "ligne")), 2)

    def test_t006_control_rate_and_relation(self) -> None:
        lot = self.service.create_lot(self.lot())
        control = self.service.add_control(self.control(lot.id_lot, defects=3))
        self.assertEqual(control.taux_defaut, 3.0)
        self.assertEqual(control.resultat, "A_CONTROLER")
        self.assertEqual(self.service.controls_for_lot(lot.id_lot), [control])

    def test_t007_inspected_quantity_above_production_is_rejected(self) -> None:
        lot = self.service.create_lot(self.lot(quantity=500))
        with self.assertRaisesRegex(ValidationError, "dépasse"):
            self.service.add_control(
                self.control(lot.id_lot, inspected=600, defects=1)
            )

    def test_t008_defects_above_inspected_quantity_are_rejected(self) -> None:
        lot = self.service.create_lot(self.lot())
        with self.assertRaisesRegex(ValidationError, "nombre de défauts"):
            self.service.add_control(
                self.control(lot.id_lot, inspected=50, defects=60)
            )

    def test_t009_configurable_thresholds_are_applied(self) -> None:
        self.assertEqual(calculate_defect_rate(3, 100), 3.0)
        self.assertEqual(determine_result(2.0, self.service.rules), "CONFORME")
        self.assertEqual(determine_result(3.0, self.service.rules), "A_CONTROLER")
        modified = dict(RULES)
        modified["thresholds"] = {
            "conforme_max": 4,
            "a_controler_max": 8,
            "abnormal_rate": 20,
        }
        (self.root / "config" / "quality_rules.json").write_text(
            json.dumps(modified), encoding="utf-8"
        )
        self.assertEqual(
            determine_result(3.0, TraceabilityService(self.root).rules), "CONFORME"
        )

    def test_t010_worst_control_result_sets_lot_status(self) -> None:
        lot = self.service.create_lot(self.lot())
        self.service.add_control(self.control(lot.id_lot, 1, defects=1))
        self.service.add_control(self.control(lot.id_lot, 2, defects=8))
        self.assertEqual(lot.statut, "REJETE")

    def test_t011_missing_control_and_abnormal_rate_are_reported(self) -> None:
        without_control = self.service.create_lot(self.lot(1))
        abnormal = self.service.create_lot(self.lot(2))
        self.service.add_control(
            self.control(abnormal.id_lot, 1, inspected=100, defects=25)
        )
        anomalies = self.service.anomalies()
        self.assertTrue(any(without_control.id_lot in item for item in anomalies))
        self.assertTrue(any("Taux anormal" in item for item in anomalies))

    def test_t012_inconsistent_status_is_detected_and_repaired(self) -> None:
        lot = self.service.create_lot(self.lot())
        self.service.add_control(self.control(lot.id_lot, defects=1))
        lot.statut = "REJETE"
        self.assertTrue(any("Statut incohérent" in item for item in self.service.anomalies()))
        self.assertEqual(self.service.repair_inconsistencies(), 1)
        self.assertEqual(lot.statut, "CONFORME")

    def test_t013_markdown_report_contains_required_sections(self) -> None:
        self.service.create_lot(self.lot())
        path = generate_report(
            self.root, self.service.lots, self.service.controls, self.service.rules
        )
        content = path.read_text(encoding="utf-8")
        for heading in (
            "Situation générale",
            "Écarts détectés",
            "Lots à examiner",
            "Défauts les plus fréquents",
            "Équipements",
        ):
            self.assertIn(heading, content)
        self.assertIn("Données fictives utilisées", content)

    def test_t014_export_persistence_json_and_manifest(self) -> None:
        lot = self.service.create_lot(self.lot())
        exported = self.service.repository.export(
            self.service.lots, self.service.controls, self.service.summary()
        )
        self.assertTrue((exported / "lots_export.csv").exists())
        self.assertTrue((exported / "controls_export.csv").exists())
        json.loads((exported / "quality_summary.json").read_text(encoding="utf-8"))
        manifest = json.loads(
            (exported / "manifest_sha256.json").read_text(encoding="utf-8")
        )
        self.assertIn("lots_export.csv", manifest)
        self.assertIsNotNone(TraceabilityService(self.root).get_lot(lot.id_lot))

    def test_t015_sample_data_can_be_restored(self) -> None:
        samples = self.root / "samples"
        samples.mkdir()
        for name, source in (
            ("lots.csv", self.service.repository.lots_path),
            ("controls.csv", self.service.repository.controls_path),
            ("audit_events.csv", self.service.repository.audit_path),
        ):
            (samples / name).write_bytes(source.read_bytes())
        self.service.create_lot(self.lot())
        self.service.repository.restore_sample_data()
        self.assertEqual(TraceabilityService(self.root).lots, [])
        self.assertTrue(self.service.repository.lots_path.with_suffix(".csv.bak").exists())

    def test_t016_console_handles_invalid_choice_without_traceback(self) -> None:
        output = StringIO()
        with patch("builtins.input", side_effect=["invalide", "0"]), redirect_stdout(output):
            ConsoleApplication(self.service, self.root).run()
        text = output.getvalue()
        self.assertIn("Choix invalide", text)
        self.assertNotIn("Traceback", text)


if __name__ == "__main__":
    unittest.main()
