"""Benchmark helper tests. No Docker or network required."""

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "benchmarks" / "load_test.py"
spec = importlib.util.spec_from_file_location("load_test", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_percentiles_use_nearest_rank():
    assert mod.percentile([10, 20, 30, 40], 50) == 20
    assert mod.percentile([10, 20, 30, 40], 95) == 40
    assert mod.percentile([], 95) is None


def test_generated_events_match_detection_rules():
    for i in range(4):
        event, should_alert = mod.event_for("loadtest-abc", i)
        assert event["event_id"] == f"loadtest-abc-{i:06d}"
        assert event["source"] == "loadtest-abc"
        assert should_alert == (i != 0)


def test_local_only_guard():
    assert mod.require_loopback("http://127.0.0.1:8000/") == "http://127.0.0.1:8000"
    for url in ("https://example.com", "http://10.0.0.3:8000", "http://localhost:8000/admin"):
        with pytest.raises(ValueError):
            mod.require_loopback(url)


def test_parse_postgres_counts():
    assert mod.parse_counts(" 100|75\n") == (100, 75)
    with pytest.raises(ValueError):
        mod.parse_counts("command failed")
