import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from radar_mqtt.inbox import InboxStore, month_ago


class MonthAgoTest(unittest.TestCase):
    def test_previous_calendar_month(self) -> None:
        self.assertEqual(month_ago(datetime(2026, 10, 3, 22, 15, 0)), datetime(2026, 9, 3, 22, 15, 0))

    def test_clamps_short_month(self) -> None:
        self.assertEqual(month_ago(datetime(2026, 3, 31, 8, 0, 0)), datetime(2026, 2, 28, 8, 0, 0))

    def test_january_goes_to_december(self) -> None:
        self.assertEqual(month_ago(datetime(2026, 1, 15, 1, 2, 3)), datetime(2025, 12, 15, 1, 2, 3))


class InboxStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.store = InboxStore(Path(self._temp.name) / "inbox.db")
        self.now = datetime(2026, 10, 3, 12, 0, 0)

    def tearDown(self) -> None:
        self.store.close()
        self._temp.cleanup()

    def test_stores_the_four_fields(self) -> None:
        self.store.record("cl/kope/iot/cafetera/alive", '{"status": "alive"}', 1, now=self.now)
        rows = self.store.list_messages(self.now)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].fecha_recepcion, "2026-10-03 12:00:00")
        self.assertEqual(rows[0].topico, "cl/kope/iot/cafetera/alive")
        self.assertEqual(rows[0].payload, '{"status": "alive"}')
        self.assertEqual(rows[0].qos, 1)

    def test_keeps_only_the_last_month_and_lists_newest_first(self) -> None:
        self.store.record("viejo", "fuera", 0, received_at=datetime(2026, 9, 3, 11, 59, 59), now=self.now)
        self.store.record("borde", "queda", 2, received_at=datetime(2026, 9, 3, 12, 0, 0), now=self.now)
        self.store.record("nuevo", "ultimo", 0, received_at=self.now, now=self.now)
        rows = self.store.list_messages(self.now)
        self.assertEqual([row.payload for row in rows], ["ultimo", "queda"])
        self.assertEqual([row.topico for row in rows], ["nuevo", "borde"])
