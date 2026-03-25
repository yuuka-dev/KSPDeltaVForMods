from __future__ import annotations

import math

import pytest

from kopdeltav.models import G0, CelestialBody, CurveKey, compute_mu, hermite_interp


class TestCurveKey:
    def test_creation(self) -> None:
        key = CurveKey(position=0.0, value=101.325, in_tangent=0.0, out_tangent=0.0)
        assert key.position == 0.0
        assert key.value == 101.325

    def test_out_tangent_independent_of_in(self) -> None:
        key = CurveKey(position=0.0, value=1.0, in_tangent=2.0, out_tangent=3.0)
        assert key.in_tangent == 2.0
        assert key.out_tangent == 3.0


class TestComputeMu:
    def test_kerbin_mu(self) -> None:
        """Kerbin: geeASL=1.0, radius=600000m -> mu=3.5316e12"""
        mu = compute_mu(gee_asl=1.0, radius=600_000.0)
        expected = 1.0 * G0 * 600_000.0**2
        assert math.isclose(mu, expected, rel_tol=1e-9)

    def test_sanctar_mu(self) -> None:
        """Sanctar: geeASL=1.1, radius=670000m -> mu ~4.8424e12"""
        mu = compute_mu(gee_asl=1.1, radius=670_000.0)
        assert math.isclose(mu, 4.8424e12, rel_tol=1e-3)


class TestCelestialBody:
    def test_mu_auto_derived(self) -> None:
        body = CelestialBody(
            name="Test",
            radius=600_000.0,
            gee_asl=1.0,
            has_ocean=False,
            atmosphere=None,
            orbit=None,
            rotational_period=21600.0,
            display_name="Test",
        )
        expected = 1.0 * G0 * 600_000.0**2
        assert math.isclose(body.mu, expected, rel_tol=1e-9)

    def test_repr_no_recursion(self) -> None:
        body = CelestialBody(
            name="Test",
            radius=600_000.0,
            gee_asl=1.0,
            has_ocean=False,
            atmosphere=None,
            orbit=None,
            rotational_period=21600.0,
            display_name="Test",
        )
        r = repr(body)
        assert "Test" in r

    def test_eq_by_name_and_radius(self) -> None:
        a = CelestialBody(
            name="X",
            radius=100.0,
            gee_asl=1.0,
            has_ocean=False,
            atmosphere=None,
            orbit=None,
            rotational_period=1.0,
            display_name="X",
        )
        b = CelestialBody(
            name="X",
            radius=100.0,
            gee_asl=2.0,
            has_ocean=True,
            atmosphere=None,
            orbit=None,
            rotational_period=2.0,
            display_name="Y",
        )
        assert a == b

    def test_hash_consistent_with_eq(self) -> None:
        a = CelestialBody(
            name="X",
            radius=100.0,
            gee_asl=1.0,
            has_ocean=False,
            atmosphere=None,
            orbit=None,
            rotational_period=1.0,
            display_name="X",
        )
        b = CelestialBody(
            name="X",
            radius=100.0,
            gee_asl=2.0,
            has_ocean=True,
            atmosphere=None,
            orbit=None,
            rotational_period=2.0,
            display_name="Y",
        )
        assert hash(a) == hash(b)


class TestHermiteInterp:
    def test_single_key_returns_value(self) -> None:
        keys = [CurveKey(0.0, 5.0, 0.0, 0.0)]
        assert hermite_interp(keys, 0.0) == 5.0
        assert hermite_interp(keys, 100.0) == 5.0

    def test_clamp_below_range(self) -> None:
        keys = [
            CurveKey(10.0, 1.0, 0.0, 0.0),
            CurveKey(20.0, 2.0, 0.0, 0.0),
        ]
        assert hermite_interp(keys, 0.0) == 1.0

    def test_clamp_above_range(self) -> None:
        keys = [
            CurveKey(10.0, 1.0, 0.0, 0.0),
            CurveKey(20.0, 2.0, 0.0, 0.0),
        ]
        assert hermite_interp(keys, 100.0) == 2.0

    def test_linear_segment_unit_tangents(self) -> None:
        """Tangent=1.0 on both sides => perfectly linear interpolation."""
        keys = [
            CurveKey(0.0, 0.0, 1.0, 1.0),
            CurveKey(10.0, 10.0, 1.0, 1.0),
        ]
        result = hermite_interp(keys, 5.0)
        assert math.isclose(result, 5.0, abs_tol=0.01)

    def test_exact_key_position(self) -> None:
        keys = [
            CurveKey(0.0, 100.0, 0.0, 0.0),
            CurveKey(50.0, 200.0, 0.0, 0.0),
        ]
        assert hermite_interp(keys, 0.0) == 100.0
        assert hermite_interp(keys, 50.0) == 200.0

    def test_empty_keys_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            hermite_interp([], 0.0)

    def test_three_segments(self) -> None:
        """Interpolation picks the correct segment."""
        keys = [
            CurveKey(0.0, 0.0, 1.0, 1.0),
            CurveKey(10.0, 10.0, 1.0, 1.0),
            CurveKey(20.0, 20.0, 1.0, 1.0),
        ]
        assert math.isclose(hermite_interp(keys, 5.0), 5.0, abs_tol=0.01)
        assert math.isclose(hermite_interp(keys, 15.0), 15.0, abs_tol=0.01)

    def test_midpoint_zero_tangents(self) -> None:
        """Zero tangents: h00(0.5)*0 + h01(0.5)*10 = 5.0."""
        keys = [
            CurveKey(0.0, 0.0, 0.0, 0.0),
            CurveKey(10.0, 10.0, 0.0, 0.0),
        ]
        result = hermite_interp(keys, 5.0)
        assert math.isclose(result, 5.0, abs_tol=0.01)
