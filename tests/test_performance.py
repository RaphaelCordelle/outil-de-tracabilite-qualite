"""Test simple du critère N-004 sur 1 000 lots fictifs."""

from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import time
import unittest

from models import Lot
from services import TraceabilityService

from test_requirements import RULES


class PerformanceTests(unittest.TestCase):
    def test_search_remains_fluid_with_one_thousand_lots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config" / "quality_rules.json").write_text(
                json.dumps(RULES), encoding="utf-8"
            )
            repository = TraceabilityService(root).repository
            days = [date.today(), date.today() - timedelta(days=1)]
            lots = [
                Lot(
                    f"LOT-{days[index // 500]:%Y%m%d}-{index % 500 + 1:03d}",
                    days[index // 500].isoformat(),
                    f"PCB_SERIE_{index % 20:02d}",
                    100 + index,
                    "LINE-01" if index % 2 == 0 else "LINE-02",
                )
                for index in range(1000)
            ]
            repository.save_lots(lots)
            start = time.perf_counter()
            service = TraceabilityService(root)
            result = service.search_lots("PCB_SERIE_07", "produit")
            elapsed = time.perf_counter() - start
            self.assertEqual(len(result), 50)
            self.assertLess(elapsed, 2.0)


if __name__ == "__main__":
    unittest.main()
