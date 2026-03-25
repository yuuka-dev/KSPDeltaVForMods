"""Tests for kopdeltav.calculator.

calculator モジュールのテスト。リファレンス値による回帰テストを含む。
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from kopdeltav.calculator import (
    calculate_hohmann,
    calculate_launch,
    calculate_tsiolkovsky,
    circular_velocity,
    density_at_altitude,
    escape_velocity,
    low_orbit_altitude,
    surface_density,
)
from kopdeltav.models import G0, CelestialBody
from kopdeltav.parser import parse_bodies

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sanctar() -> CelestialBody:
    """Parse Sanctar from the sample config.

    The config replaces Kerbin with Sanctar, so the parsed name is "Kerbin"
    but the physical properties (radius=670 000, geeASL=1.1) are Sanctar's.
    """
    cfg_path = Path(__file__).resolve().parent.parent / "sample_configs" / "Sanctar.cfg"
    bodies = parse_bodies(cfg_path.read_text(encoding="utf-8"))
    assert len(bodies) >= 1
    return bodies[0]


def _make_airless_body() -> CelestialBody:
    """Create a simple airless body for testing (Mun-like)."""
    return CelestialBody(
        name="Airless",
        radius=200_000.0,
        gee_asl=0.138,
        has_ocean=False,
        atmosphere=None,
        orbit=None,
        rotational_period=138_984.0,
        display_name="Airless",
    )


# ---------------------------------------------------------------------------
# Tests: low_orbit_altitude
# ---------------------------------------------------------------------------


class TestLowOrbitAltitude:
    def test_with_atmosphere(self) -> None:
        sanctar = _make_sanctar()
        alt = low_orbit_altitude(sanctar)
        assert sanctar.atmosphere is not None
        assert alt > sanctar.atmosphere.atmosphere_depth
        assert alt < sanctar.atmosphere.atmosphere_depth * 2.0

    def test_airless_body(self) -> None:
        body = _make_airless_body()
        alt = low_orbit_altitude(body)
        assert alt >= 10_000.0

    def test_tiny_airless_body(self) -> None:
        """Minimum altitude is 10 000 m even for very small bodies."""
        body = CelestialBody(
            name="Tiny",
            radius=5_000.0,
            gee_asl=0.01,
            has_ocean=False,
            atmosphere=None,
            orbit=None,
            rotational_period=1000.0,
            display_name="Tiny",
        )
        assert low_orbit_altitude(body) >= 10_000.0


# ---------------------------------------------------------------------------
# Tests: circular_velocity
# ---------------------------------------------------------------------------


class TestCircularVelocity:
    def test_sanctar_80km(self) -> None:
        """Reference: v_circular at 80 km = 2541.1 m/s."""
        sanctar = _make_sanctar()
        v = circular_velocity(sanctar, 80_000.0)
        assert math.isclose(v, 2541.1, rel_tol=1e-3)

    def test_surface(self) -> None:
        sanctar = _make_sanctar()
        v = circular_velocity(sanctar, 0.0)
        expected = math.sqrt(sanctar.mu / sanctar.radius)
        assert math.isclose(v, expected, rel_tol=1e-9)

    def test_negative_altitude_raises(self) -> None:
        body = _make_airless_body()
        with pytest.raises(ValueError, match="non-negative"):
            circular_velocity(body, -100.0)


# ---------------------------------------------------------------------------
# Tests: escape_velocity
# ---------------------------------------------------------------------------


class TestEscapeVelocity:
    def test_sanctar_surface(self) -> None:
        """Reference: escape velocity at surface = 3802.0 m/s."""
        sanctar = _make_sanctar()
        v = escape_velocity(sanctar, 0.0)
        assert math.isclose(v, 3802.0, rel_tol=1e-3)

    def test_sqrt2_relation(self) -> None:
        """v_escape = sqrt(2) * v_circular at the same altitude."""
        sanctar = _make_sanctar()
        v_c = circular_velocity(sanctar, 80_000.0)
        v_e = escape_velocity(sanctar, 80_000.0)
        assert math.isclose(v_e, v_c * math.sqrt(2), rel_tol=1e-9)

    def test_negative_altitude_raises(self) -> None:
        body = _make_airless_body()
        with pytest.raises(ValueError, match="non-negative"):
            escape_velocity(body, -100.0)


# ---------------------------------------------------------------------------
# Tests: surface_density & density_at_altitude
# ---------------------------------------------------------------------------


class TestSurfaceDensity:
    def test_sanctar_reference(self) -> None:
        """Reference: sea-level density = 1.4096 kg/m³."""
        sanctar = _make_sanctar()
        rho = surface_density(sanctar)
        assert rho is not None
        assert math.isclose(rho, 1.4096, rel_tol=1e-3)

    def test_airless_returns_none(self) -> None:
        body = _make_airless_body()
        assert surface_density(body) is None


class TestDensityAtAltitude:
    def test_zero_matches_surface(self) -> None:
        sanctar = _make_sanctar()
        rho_s = surface_density(sanctar)
        rho_0 = density_at_altitude(sanctar, 0.0)
        assert rho_s is not None and rho_0 is not None
        assert math.isclose(rho_s, rho_0, rel_tol=1e-9)

    def test_above_atmosphere_is_zero(self) -> None:
        sanctar = _make_sanctar()
        assert sanctar.atmosphere is not None
        rho = density_at_altitude(sanctar, sanctar.atmosphere.atmosphere_depth + 1000.0)
        assert rho == 0.0

    def test_decreases_with_altitude(self) -> None:
        sanctar = _make_sanctar()
        rho_0 = density_at_altitude(sanctar, 0.0)
        rho_10k = density_at_altitude(sanctar, 10_000.0)
        rho_30k = density_at_altitude(sanctar, 30_000.0)
        assert rho_0 is not None and rho_10k is not None and rho_30k is not None
        assert rho_0 > rho_10k > rho_30k > 0.0

    def test_airless_returns_none(self) -> None:
        body = _make_airless_body()
        assert density_at_altitude(body, 0.0) is None


# ---------------------------------------------------------------------------
# Tests: calculate_launch
# ---------------------------------------------------------------------------


class TestCalculateLaunch:
    def test_sanctar_reference_values(self) -> None:
        """Regression: Sanctar launch ΔV ≈ 3110 (rocket), ≈ 1982 (jets)."""
        sanctar = _make_sanctar()
        r = calculate_launch(sanctar, 80_000.0)

        assert math.isclose(r.orbital_velocity, 2541.1, rel_tol=1e-3)
        assert math.isclose(r.total_ideal, r.orbital_velocity, rel_tol=1e-9)
        assert math.isclose(r.total_rocket, 3110.0, rel_tol=0.05)
        assert math.isclose(r.total_with_jets, 1982.0, rel_tol=0.05)

    def test_losses_positive_with_atmosphere(self) -> None:
        sanctar = _make_sanctar()
        r = calculate_launch(sanctar, 80_000.0)
        assert r.gravity_loss > 0
        assert r.drag_loss > 0
        assert r.jet_savings > 0
        assert r.total_with_jets < r.total_rocket

    def test_airless_no_drag_no_jets(self) -> None:
        body = _make_airless_body()
        r = calculate_launch(body, 10_000.0)
        assert r.drag_loss == 0.0
        assert r.jet_savings == 0.0
        assert r.total_with_jets == r.total_rocket
        assert r.gravity_loss > 0

    def test_consistency(self) -> None:
        """total_rocket = orbital_velocity + gravity_loss + drag_loss."""
        sanctar = _make_sanctar()
        r = calculate_launch(sanctar, 80_000.0)
        assert math.isclose(r.total_rocket, r.orbital_velocity + r.gravity_loss + r.drag_loss)
        assert math.isclose(r.total_with_jets, r.total_rocket - r.jet_savings)

    def test_negative_altitude_raises(self) -> None:
        body = _make_airless_body()
        with pytest.raises(ValueError, match="non-negative"):
            calculate_launch(body, -1.0)


# ---------------------------------------------------------------------------
# Tests: calculate_hohmann
# ---------------------------------------------------------------------------


class TestCalculateHohmann:
    def test_basic_transfer(self) -> None:
        """80 km → 200 km around Sanctar."""
        sanctar = _make_sanctar()
        r2 = sanctar.radius + 200_000.0
        result = calculate_hohmann(sanctar, 80_000.0, r2)

        assert result.departure_dv > 0
        assert result.arrival_dv > 0
        assert math.isclose(result.total_dv, result.departure_dv + result.arrival_dv)
        assert result.transfer_time > 0

    def test_departure_dv_formula(self) -> None:
        """Verify departure ΔV against manual vis-viva computation."""
        sanctar = _make_sanctar()
        r1 = sanctar.radius + 80_000.0
        r2 = sanctar.radius + 200_000.0
        mu = sanctar.mu
        a_t = (r1 + r2) / 2.0

        v1 = math.sqrt(mu / r1)
        v_tp = math.sqrt(mu * (2.0 / r1 - 1.0 / a_t))
        expected = v_tp - v1

        result = calculate_hohmann(sanctar, 80_000.0, r2)
        assert math.isclose(result.departure_dv, expected, rel_tol=1e-9)

    def test_arrival_dv_formula(self) -> None:
        """Verify arrival ΔV against manual vis-viva computation."""
        sanctar = _make_sanctar()
        r1 = sanctar.radius + 80_000.0
        r2 = sanctar.radius + 200_000.0
        mu = sanctar.mu
        a_t = (r1 + r2) / 2.0

        v2 = math.sqrt(mu / r2)
        v_ta = math.sqrt(mu * (2.0 / r2 - 1.0 / a_t))
        expected = v2 - v_ta

        result = calculate_hohmann(sanctar, 80_000.0, r2)
        assert math.isclose(result.arrival_dv, expected, rel_tol=1e-9)

    def test_transfer_time_formula(self) -> None:
        """Verify transfer_time = π√(a³/μ)."""
        sanctar = _make_sanctar()
        r1 = sanctar.radius + 80_000.0
        r2 = sanctar.radius + 200_000.0
        a_t = (r1 + r2) / 2.0
        expected_time = math.pi * math.sqrt(a_t**3 / sanctar.mu)

        result = calculate_hohmann(sanctar, 80_000.0, r2)
        assert math.isclose(result.transfer_time, expected_time, rel_tol=1e-9)

    def test_target_below_parking_raises(self) -> None:
        sanctar = _make_sanctar()
        with pytest.raises(ValueError, match="larger"):
            calculate_hohmann(sanctar, 80_000.0, 700_000.0)

    def test_negative_parking_raises(self) -> None:
        sanctar = _make_sanctar()
        with pytest.raises(ValueError, match="non-negative"):
            calculate_hohmann(sanctar, -100.0, 900_000.0)


# ---------------------------------------------------------------------------
# Tests: calculate_tsiolkovsky
# ---------------------------------------------------------------------------


class TestCalculateTsiolkovsky:
    def test_basic(self) -> None:
        """Δv=3110, Isp=340 s, wet=10 000 kg."""
        result = calculate_tsiolkovsky(3110.0, 340.0, 10_000.0)

        ve = 340.0 * G0
        expected_ratio = math.exp(3110.0 / ve)
        assert math.isclose(result.mass_ratio, expected_ratio, rel_tol=1e-9)
        assert math.isclose(result.fuel_fraction, 1.0 - 1.0 / expected_ratio, rel_tol=1e-9)
        assert math.isclose(result.dry_mass, 10_000.0 / expected_ratio, rel_tol=1e-9)
        assert math.isclose(result.fuel_mass, 10_000.0 - result.dry_mass, rel_tol=1e-9)

    def test_zero_delta_v(self) -> None:
        result = calculate_tsiolkovsky(0.0, 340.0, 10_000.0)
        assert math.isclose(result.mass_ratio, 1.0)
        assert math.isclose(result.fuel_fraction, 0.0, abs_tol=1e-12)
        assert math.isclose(result.dry_mass, 10_000.0)
        assert math.isclose(result.fuel_mass, 0.0, abs_tol=1e-9)

    def test_mass_conservation(self) -> None:
        result = calculate_tsiolkovsky(5000.0, 380.0, 50_000.0)
        assert math.isclose(result.dry_mass + result.fuel_mass, 50_000.0, rel_tol=1e-9)

    def test_negative_dv_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            calculate_tsiolkovsky(-100.0, 340.0, 10_000.0)

    def test_zero_isp_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            calculate_tsiolkovsky(1000.0, 0.0, 10_000.0)

    def test_zero_mass_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            calculate_tsiolkovsky(1000.0, 340.0, 0.0)
