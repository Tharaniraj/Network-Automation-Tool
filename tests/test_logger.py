"""
Unit tests for modules/logger.py
"""

import json
import tempfile
import threading
import unittest
from pathlib import Path

from modules.logger import ObservabilityManager


def _make_manager(tmp_path: str) -> ObservabilityManager:
    return ObservabilityManager(log_dir=tmp_path)


class TestLogEvent(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mgr = _make_manager(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_event_written_to_file(self):
        self.mgr.log_event("device_added", "r1", "Device added", status="success")
        with open(self.mgr.events_file) as f:
            data = json.load(f)
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["events"][0]["type"], "device_added")

    def test_event_has_required_fields(self):
        self.mgr.log_event("test_event", "r1", "test description")
        with open(self.mgr.events_file) as f:
            event = json.load(f)["events"][0]
        for field in ("timestamp", "type", "device", "description", "status"):
            self.assertIn(field, event)

    def test_get_device_events_filtered(self):
        self.mgr.log_event("e1", "r1", "desc1")
        self.mgr.log_event("e2", "r2", "desc2")
        events = self.mgr.get_device_events("r1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "e1")

    def test_get_device_events_limit(self):
        for i in range(10):
            self.mgr.log_event("evt", "r1", f"desc {i}")
        events = self.mgr.get_device_events("r1", limit=3)
        self.assertEqual(len(events), 3)


class TestLogMetric(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mgr = _make_manager(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_metric_written(self):
        self.mgr.log_metric("r1", "cpu_usage", 45.0, "%")
        with open(self.mgr.telemetry_file) as f:
            data = json.load(f)
        self.assertEqual(len(data["metrics"]), 1)
        self.assertEqual(data["metrics"][0]["metric"], "cpu_usage")
        self.assertEqual(data["metrics"][0]["value"], 45.0)

    def test_get_device_metrics(self):
        self.mgr.log_metric("r1", "cpu", 30, "%")
        self.mgr.log_metric("r2", "cpu", 50, "%")
        metrics = self.mgr.get_device_metrics("r1")
        self.assertEqual(len(metrics), 1)


class TestLogError(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mgr = _make_manager(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_error_event_written(self):
        self.mgr.log_error("r1", "Something went wrong", "ssh_error")
        with open(self.mgr.events_file) as f:
            events = json.load(f)["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["error_type"], "ssh_error")


class TestEntryCap(unittest.TestCase):
    """Verify that the event file is pruned once _MAX_EVENTS is reached."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_entries_pruned_at_cap(self):
        import modules.logger as logger_module
        original_max = logger_module._MAX_EVENTS
        logger_module._MAX_EVENTS = 5
        try:
            mgr = _make_manager(self.tmp.name)
            for i in range(10):
                mgr.log_event("evt", "r1", f"msg {i}")
            with open(mgr.events_file) as f:
                events = json.load(f)["events"]
            self.assertLessEqual(len(events), 5)
        finally:
            logger_module._MAX_EVENTS = original_max


class TestThreadSafety(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mgr = _make_manager(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_concurrent_writes_no_corruption(self):
        """Concurrent log_event calls must not corrupt the JSON file."""
        errors = []

        def _write(i):
            try:
                self.mgr.log_event("evt", f"device-{i}", f"concurrent write {i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_write, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Errors during concurrent writes: {errors}")

        with open(self.mgr.events_file) as f:
            data = json.load(f)  # must be valid JSON
        self.assertIn("events", data)


class TestSummaryStats(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mgr = _make_manager(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_summary_reflects_events(self):
        self.mgr.log_event("config_backup", "r1", "backed up", status="success")
        self.mgr.log_error("r1", "oops", "error")
        stats = self.mgr.get_summary_stats()
        self.assertEqual(stats["total_events"], 2)
        self.assertGreaterEqual(stats["config_changes"], 1)


if __name__ == "__main__":
    unittest.main()
