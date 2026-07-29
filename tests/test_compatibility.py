"""Garde-fou de compatibilité avec l'interpréteur Python 3.8 d'EduPython."""

import ast
from pathlib import Path
import unittest


class CompatibilityTests(unittest.TestCase):
    def test_all_application_modules_parse_with_python_38_grammar(self) -> None:
        root = Path(__file__).resolve().parents[1]
        modules = [path for path in root.glob("*.py")]
        self.assertTrue(modules)
        for module in modules:
            with self.subTest(module=module.name):
                source = module.read_text(encoding="utf-8")
                ast.parse(source, filename=str(module), feature_version=(3, 8))
                self.assertNotIn("slots=True", source)


if __name__ == "__main__":
    unittest.main()
