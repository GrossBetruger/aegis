"""
Deterministic unit tests for naval force scoring using static USNI Fleet Tracker
HTML snapshots from Dec 2025 – Feb 2026. No network calls; pure function tests.
"""

import json
import os

import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from update_data import score_naval_force

FIXTURES_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "fleet_tracker_snapshots.json"
)


@pytest.fixture(scope="module")
def fixtures():
    with open(FIXTURES_PATH) as f:
        return json.load(f)


class TestNavalBuildupScoring:

    # ---- Exact value assertions (deterministic) ----

    def test_baseline_dec29_exact_values(self, fixtures):
        result = score_naval_force(fixtures["2025-12-29"])
        assert result["total_weighted_points"] == 18.0
        assert result["force_risk"] == 0
        assert result["carriers_in_centcom"] == 0
        assert result["destroyers_in_centcom"] == 3

    def test_pre_buildup_jan20_exact_values(self, fixtures):
        result = score_naval_force(fixtures["2026-01-20"])
        assert result["total_weighted_points"] == 15.6
        assert result["force_risk"] == 0
        assert result["carriers_in_centcom"] == 0

    def test_lincoln_arrives_jan26_exact_values(self, fixtures):
        result = score_naval_force(fixtures["2026-01-26"])
        assert result["total_weighted_points"] == 50.2
        assert result["force_risk"] == 18
        assert result["carriers_in_centcom"] == 1
        assert result["destroyers_in_centcom"] == 6

    def test_ford_ordered_feb17_exact_values(self, fixtures):
        result = score_naval_force(fixtures["2026-02-17"])
        assert result["total_weighted_points"] == 77.7
        assert result["force_risk"] == 50
        assert result["carriers_in_centcom"] == 2
        assert result["destroyers_in_centcom"] == 11

    # ---- Strict monotonic increase across buildup phase ----

    def test_buildup_points_strictly_increasing(self, fixtures):
        r1 = score_naval_force(fixtures["2026-01-20"])
        r2 = score_naval_force(fixtures["2026-01-26"])
        r3 = score_naval_force(fixtures["2026-02-17"])
        assert r1["total_weighted_points"] < r2["total_weighted_points"] < r3["total_weighted_points"]

    def test_buildup_risk_strictly_increasing(self, fixtures):
        r1 = score_naval_force(fixtures["2026-01-20"])
        r2 = score_naval_force(fixtures["2026-01-26"])
        r3 = score_naval_force(fixtures["2026-02-17"])
        assert r1["force_risk"] < r2["force_risk"] < r3["force_risk"]

    def test_buildup_carriers_monotonically_increasing(self, fixtures):
        r1 = score_naval_force(fixtures["2026-01-20"])
        r2 = score_naval_force(fixtures["2026-01-26"])
        r3 = score_naval_force(fixtures["2026-02-17"])
        assert r1["carriers_in_centcom"] <= r2["carriers_in_centcom"] <= r3["carriers_in_centcom"]
        assert r3["carriers_in_centcom"] > r1["carriers_in_centcom"]

    # ---- Carrier arrival impact assertions ----

    def test_lincoln_arrival_adds_at_least_30_points(self, fixtures):
        pre = score_naval_force(fixtures["2026-01-20"])
        post = score_naval_force(fixtures["2026-01-26"])
        assert post["total_weighted_points"] - pre["total_weighted_points"] >= 30

    def test_ford_transit_adds_at_least_20_points(self, fixtures):
        pre = score_naval_force(fixtures["2026-01-26"])
        post = score_naval_force(fixtures["2026-02-17"])
        assert post["total_weighted_points"] - pre["total_weighted_points"] >= 20

    # ---- Baseline phase assertions ----

    def test_baseline_phase_zero_risk(self, fixtures):
        r_dec = score_naval_force(fixtures["2025-12-29"])
        r_jan = score_naval_force(fixtures["2026-01-20"])
        assert r_dec["force_risk"] == 0
        assert r_jan["force_risk"] == 0

    def test_baseline_phase_no_carriers(self, fixtures):
        r_dec = score_naval_force(fixtures["2025-12-29"])
        r_jan = score_naval_force(fixtures["2026-01-20"])
        assert r_dec["carriers_in_centcom"] == 0
        assert r_jan["carriers_in_centcom"] == 0
