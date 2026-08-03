"""Tests des trois vues proposées dans l'interface."""

import json
from pathlib import Path
import tempfile
import unittest

from access import MODE_LABELS, has_permission
from gui import QualityTraceabilityApp
from quality_rules import ValidationError
from services import TraceabilityService
from test_requirements import RULES


class AccessModeTests(unittest.TestCase):
    def test_each_mode_has_a_limited_and_readable_scope(self) -> None:
        self.assertEqual(set(MODE_LABELS), {"EMPLOYE", "QUALITE", "MANAGER"})
        self.assertTrue(has_permission("EMPLOYE", "report_issue"))
        self.assertFalse(has_permission("EMPLOYE", "validate_controls"))
        self.assertTrue(has_permission("QUALITE", "validate_controls"))
        self.assertFalse(has_permission("QUALITE", "configure_rules"))
        self.assertTrue(has_permission("MANAGER", "configure_rules"))
        self.assertTrue(has_permission("MANAGER", "view_audit"))

    def test_navigation_is_adapted_to_the_selected_mode(self) -> None:
        employee = QualityTraceabilityApp.MODE_NAVIGATION["EMPLOYE"]
        quality = QualityTraceabilityApp.MODE_NAVIGATION["QUALITE"]
        manager = QualityTraceabilityApp.MODE_NAVIGATION["MANAGER"]
        self.assertNotIn("anomalies", employee)
        self.assertNotIn("settings", employee)
        self.assertIn("anomalies", quality)
        self.assertNotIn("audit", quality)
        self.assertNotIn("settings", quality)
        self.assertIn("audit", manager)
        self.assertIn("settings", manager)
        self.assertEqual(manager, {item[0] for item in QualityTraceabilityApp.NAVIGATION})

    def test_display_mode_is_saved_without_creating_a_business_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config" / "quality_rules.json").write_text(
                json.dumps(RULES), encoding="utf-8"
            )
            service = TraceabilityService(root)
            self.assertEqual(service.rules["interface_mode"], "QUALITE")
            saved = json.loads(
                (root / "config" / "quality_rules.json").read_text(encoding="utf-8")
            )
            self.assertEqual(saved["interface_mode"], "QUALITE")

            events_before = service.repository.load_audit_events()
            service.update_interface_mode("MANAGER")

            reloaded = TraceabilityService(root)
            self.assertEqual(reloaded.rules["interface_mode"], "MANAGER")
            self.assertEqual(reloaded.repository.load_audit_events(), events_before)

    def test_unknown_display_mode_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config" / "quality_rules.json").write_text(
                json.dumps(RULES), encoding="utf-8"
            )
            service = TraceabilityService(root)
            with self.assertRaises(ValidationError):
                service.update_interface_mode("ADMIN")


if __name__ == "__main__":
    unittest.main()
