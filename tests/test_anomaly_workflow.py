"""Tests du cycle de vie persistant des anomalies."""

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from models import ControleQualite, Lot
from quality_rules import ValidationError
from services import TraceabilityService
from test_requirements import RULES


class AnomalyWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "config").mkdir()
        (self.root / "config" / "quality_rules.json").write_text(
            json.dumps(RULES), encoding="utf-8"
        )
        self.service = TraceabilityService(self.root)
        self.today = date.today()
        self.code = self.today.strftime("%Y%m%d")
        self.iso = self.today.isoformat()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_lot(self) -> Lot:
        return self.service.create_lot(
            Lot(
                f"LOT-{self.code}-001",
                self.iso,
                "PCB_ANO_A1",
                100,
                "LINE-01",
            )
        )

    def add_control(self, lot: Lot) -> ControleQualite:
        return self.service.add_control(
            ControleQualite(
                f"QC-{self.code}-001",
                lot.id_lot,
                self.iso,
                100,
                1,
                "DEFAUT_VISUEL",
                0,
                "",
            )
        )

    def test_detection_creates_and_persists_tracking_record(self) -> None:
        lot = self.create_lot()
        tracking = self.service.synchronize_anomalies()
        self.assertEqual(len(tracking), 1)
        self.assertEqual(tracking[0].entite_id, lot.id_lot)
        self.assertEqual(tracking[0].statut, "NOUVELLE")
        reloaded = TraceabilityService(self.root)
        self.assertEqual(
            reloaded.require_tracked_anomaly(tracking[0].id_anomalie).cle_anomalie,
            tracking[0].cle_anomalie,
        )

    def test_ignored_anomaly_requires_reason_and_leaves_active_view(self) -> None:
        self.create_lot()
        anomaly = self.service.synchronize_anomalies()[0]
        with self.assertRaisesRegex(ValidationError, "motif"):
            self.service.update_anomaly_tracking(
                anomaly.id_anomalie, statut="IGNOREE"
            )
        self.service.update_anomaly_tracking(
            anomaly.id_anomalie,
            statut="IGNOREE",
            commentaire="Écart accepté pour cette séquence.",
        )
        self.assertEqual(self.service.active_tracked_anomalies(), [])
        self.assertEqual(anomaly.statut, "IGNOREE")

    def test_active_cause_cannot_be_marked_resolved(self) -> None:
        self.create_lot()
        anomaly = self.service.synchronize_anomalies()[0]
        with self.assertRaisesRegex(ValidationError, "encore présente"):
            self.service.update_anomaly_tracking(
                anomaly.id_anomalie,
                statut="RESOLUE",
                commentaire="Tentative",
            )

    def test_ignored_anomaly_must_be_reopened_before_processing(self) -> None:
        self.create_lot()
        anomaly = self.service.synchronize_anomalies()[0]
        self.service.update_anomaly_tracking(
            anomaly.id_anomalie,
            statut="IGNOREE",
            commentaire="Écart accepté temporairement.",
        )
        with self.assertRaisesRegex(ValidationError, "Passage impossible"):
            self.service.update_anomaly_tracking(
                anomaly.id_anomalie,
                statut="EN_COURS",
                commentaire="Reprise directe",
            )
        self.service.update_anomaly_tracking(
            anomaly.id_anomalie,
            statut="NOUVELLE",
            commentaire="Nouvelle vérification demandée.",
        )
        self.assertEqual(anomaly.statut, "NOUVELLE")

    def test_anomaly_is_resolved_automatically_when_cause_disappears(self) -> None:
        lot = self.create_lot()
        anomaly = self.service.synchronize_anomalies()[0]
        self.add_control(lot)
        self.service.synchronize_anomalies()
        self.assertEqual(anomaly.statut, "RESOLUE")
        self.assertTrue(anomaly.date_resolution)

    def test_repair_resolves_derived_inconsistency_and_export_keeps_history(self) -> None:
        lot = self.create_lot()
        control = self.add_control(lot)
        self.service.synchronize_anomalies()
        control.taux_defaut = 99.0
        self.service.repository.save_controls(self.service.controls)
        active = self.service.synchronize_anomalies()
        rate_anomaly = next(
            item for item in active if item.type_anomalie == "TAUX_INCOHERENT"
        )
        self.service.repair_inconsistencies()
        self.assertEqual(rate_anomaly.statut, "RESOLUE")
        exported = self.service.repository.export(
            self.service.lots,
            self.service.controls,
            self.service.summary(),
            self.service.equipment,
            self.service.equipment_issues,
            self.service.equipment_usage,
            self.service.tracked_anomalies(),
        )
        self.assertTrue((exported / "anomaly_tracking_export.csv").exists())


if __name__ == "__main__":
    unittest.main()
