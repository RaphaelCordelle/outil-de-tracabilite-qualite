"""Tests de robustesse au-delà des critères d'acceptation minimaux."""

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from models import ControleQualite, Lot
from quality_rules import ValidationError
from services import TraceabilityService
from storage import StorageError

from test_requirements import RULES


class RobustnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "config").mkdir()
        (self.root / "config" / "quality_rules.json").write_text(
            json.dumps(RULES), encoding="utf-8"
        )
        self.service = TraceabilityService(self.root)
        self.code = date.today().strftime("%Y%m%d")
        self.iso = date.today().isoformat()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_corrupt_csv_header_has_actionable_message(self) -> None:
        self.service.repository.lots_path.write_text("bad,header\n1,2\n", encoding="utf-8")
        with self.assertRaisesRegex(StorageError, "En-tête invalide"):
            TraceabilityService(self.root)

    def test_non_numeric_csv_value_identifies_line(self) -> None:
        self.service.repository.lots_path.write_text(
            "id_lot,date_creation,produit,quantite_produite,ligne_production,statut,commentaire\n"
            f"LOT-{self.code}-001,{self.iso},PCB_A1,abc,LINE-01,SANS_CONTROLE,\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(StorageError, "ligne 2"):
            TraceabilityService(self.root)

    def test_invalid_json_configuration_is_rejected(self) -> None:
        (self.root / "config" / "quality_rules.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(StorageError, "JSON illisible"):
            TraceabilityService(self.root)

    def test_archive_is_reversible_and_blocks_new_controls(self) -> None:
        lot = self.service.create_lot(
            Lot(f"LOT-{self.code}-001", self.iso, "PCB_A1", 100, "LINE-01")
        )
        self.service.archive_lot(lot.id_lot)
        control = ControleQualite(
            f"QC-{self.code}-001",
            lot.id_lot,
            self.iso,
            10,
            0,
            "DEFAUT_VISUEL",
            0,
            "",
        )
        with self.assertRaisesRegex(ValidationError, "archivé"):
            self.service.add_control(control)
        self.service.restore_lot(lot.id_lot)
        self.assertEqual(lot.statut, "SANS_CONTROLE")

    def test_audit_records_important_business_events(self) -> None:
        lot = self.service.create_lot(
            Lot(f"LOT-{self.code}-001", self.iso, "PCB_A1", 100, "LINE-01")
        )
        self.service.update_lot(lot.id_lot, commentaire="Revue")
        self.service.archive_lot(lot.id_lot)
        events = self.service.repository.load_audit_events()
        self.assertEqual(
            [event["evenement"] for event in events],
            ["LOT_CREE", "LOT_MODIFIE", "LOT_ARCHIVE"],
        )

    def test_automatic_identifiers_are_unique(self) -> None:
        first = self.service.next_lot_id()
        self.service.create_lot(Lot(first, self.iso, "PCB_A1", 100, "LINE-01"))
        self.assertNotEqual(first, self.service.next_lot_id())

    def test_control_can_be_updated_and_recalculates_lot(self) -> None:
        lot = self.service.create_lot(
            Lot(f"LOT-{self.code}-001", self.iso, "PCB_A1", 100, "LINE-01")
        )
        control = self.service.add_control(
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
        updated = self.service.update_control(
            control.id_controle,
            nombre_defauts=8,
            commentaire="Écart confirmé",
        )
        self.assertEqual(updated.taux_defaut, 8.0)
        self.assertEqual(updated.resultat, "REJETE")
        self.assertEqual(lot.statut, "REJETE")
        reloaded = TraceabilityService(self.root)
        self.assertEqual(
            reloaded.require_control(control.id_controle).commentaire,
            "Écart confirmé",
        )

    def test_only_validated_controls_feed_operational_indicators(self) -> None:
        lot = self.service.create_lot(
            Lot(f"LOT-{self.code}-001", self.iso, "PCB_A1", 100, "LINE-01")
        )
        control = ControleQualite(
            f"QC-{self.code}-001",
            lot.id_lot,
            self.iso,
            100,
            10,
            "DEFAUT_VISUEL",
            0,
            "",
            etat_controle="EN_ATTENTE",
        )
        self.service.add_control(control)
        self.assertEqual(lot.statut, "SANS_CONTROLE")
        self.assertEqual(self.service.summary().total_controles, 0)
        self.service.update_control(control.id_controle, etat_controle="VALIDE")
        self.assertEqual(lot.statut, "REJETE")
        self.assertEqual(self.service.summary().total_controles, 1)
        self.service.update_control(control.id_controle, etat_controle="ANNULE")
        self.assertEqual(lot.statut, "SANS_CONTROLE")
        self.assertEqual(self.service.summary().quantite_controlee, 0)

    def test_legacy_controls_csv_is_migrated_with_backup(self) -> None:
        lot = self.service.create_lot(
            Lot(f"LOT-{self.code}-001", self.iso, "PCB_A1", 100, "LINE-01")
        )
        self.service.repository.controls_path.write_text(
            "id_controle,id_lot,date_controle,quantite_controlee,nombre_defauts,"
            "type_defaut,taux_defaut,resultat,commentaire\n"
            f"QC-{self.code}-001,{lot.id_lot},{self.iso},10,0,"
            "DEFAUT_VISUEL,0.0,CONFORME,Historique\n",
            encoding="utf-8",
        )
        migrated = TraceabilityService(self.root)
        self.assertEqual(migrated.controls[0].etat_controle, "VALIDE")
        self.assertTrue(
            migrated.repository.controls_path.with_suffix(".csv.bak").exists()
        )
        self.assertIn(
            "etat_controle",
            migrated.repository.controls_path.read_text(encoding="utf-8").splitlines()[0],
        )

    def test_legacy_audit_file_receives_a_profile_column(self) -> None:
        legacy = (
            "horodatage,evenement,type_entite,id_entite,details\n"
            "2026-07-01T09:00:00+02:00,LOT_CREE,LOT,LOT-20260701-001,Création\n"
        )
        self.service.repository.audit_path.write_text(legacy, encoding="utf-8")

        reloaded = TraceabilityService(self.root)
        events = reloaded.repository.load_audit_events()

        self.assertEqual(events[0]["profil"], "SYSTEME")


if __name__ == "__main__":
    unittest.main()
