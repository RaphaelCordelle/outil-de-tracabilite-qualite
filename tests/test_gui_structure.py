"""Tests sans écran des points d'entrée de l'interface graphique."""

import ast
from datetime import date
import inspect
import json
from pathlib import Path
import tempfile
import textwrap
import unittest

from gui import QualityTraceabilityApp
from gui_dialogs import ControlDialog, LotDialog
from main import build_parser
from models import ControleQualite, Lot
from services import TraceabilityService

from test_requirements import RULES


class GuiStructureTests(unittest.TestCase):
    def test_navigation_contains_all_expected_business_pages(self) -> None:
        keys = [item[0] for item in QualityTraceabilityApp.NAVIGATION]
        self.assertEqual(
            keys,
            [
                "dashboard",
                "lots",
                "controls",
                "equipment",
                "anomalies",
                "reports",
                "audit",
                "settings",
            ],
        )

    def test_default_command_is_gui_and_console_remains_available(self) -> None:
        parser = build_parser()
        self.assertIsNone(parser.parse_args([]).command)
        self.assertEqual(parser.parse_args(["gui"]).command, "gui")
        self.assertEqual(parser.parse_args(["console"]).command, "console")

    def test_dialog_initializers_use_the_injected_service(self) -> None:
        for dialog in (LotDialog, ControlDialog):
            tree = ast.parse(textwrap.dedent(inspect.getsource(dialog.__init__)))
            undefined_service_names = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Name)
                and node.id == "service"
                and isinstance(node.ctx, ast.Load)
            ]
            self.assertEqual(
                undefined_service_names,
                [],
                f"{dialog.__name__} utilise un service local non défini.",
            )

    def test_rule_update_recalculates_control_and_lot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config" / "quality_rules.json").write_text(
                json.dumps(RULES), encoding="utf-8"
            )
            service = TraceabilityService(root)
            current = date.today()
            code = current.strftime("%Y%m%d")
            lot = service.create_lot(
                Lot(
                    f"LOT-{code}-001",
                    current.isoformat(),
                    "PCB_GUI_A1",
                    100,
                    "LINE-01",
                )
            )
            service.add_control(
                ControleQualite(
                    f"QC-{code}-001",
                    lot.id_lot,
                    current.isoformat(),
                    100,
                    3,
                    "DEFAUT_VISUEL",
                    0,
                    "",
                )
            )
            updated = dict(RULES)
            updated["thresholds"] = {
                "conforme_max": 4,
                "a_controler_max": 8,
                "abnormal_rate": 20,
            }
            corrections = service.update_rules(updated)
            self.assertGreaterEqual(corrections, 2)
            self.assertEqual(lot.statut, "CONFORME")
            self.assertEqual(service.controls[0].resultat, "CONFORME")
            reloaded = TraceabilityService(root)
            self.assertEqual(reloaded.rules["thresholds"]["conforme_max"], 4)
            self.assertEqual(reloaded.require_lot(lot.id_lot).statut, "CONFORME")


if __name__ == "__main__":
    unittest.main()
