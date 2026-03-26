"""Tests for kopdeltav.calculator.

calculator モジュールのテスト。リファレンス値による回帰テストを含む。
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from kopdeltav.calculator import (
    DvStep,
    calculate_hohmann,
    calculate_launch,
    calculate_tsiolkovsky,
    circular_velocity,
    compute_route,
    density_at_altitude,
    escape_dv_from_low_orbit,
    escape_velocity,
    geostationary_altitude,
    geostationary_dv,
    landing_dv,
    low_orbit_altitude,
    surface_density,
)
from kopdeltav.models import G0, CelestialBody, OrbitalElements
from kopdeltav.parser import parse_bodies
from kopdeltav.system import build_tree

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

    def test_inward_transfer(self) -> None:
        """Hohmann transfer to inner orbit (r2 < r1) must work and set inward=True."""
        sanctar = _make_sanctar()
        r_inner = sanctar.radius + 20_000.0
        result = calculate_hohmann(sanctar, 80_000.0, r_inner)
        assert result.inward is True
        assert result.departure_dv > 0
        assert result.arrival_dv > 0
        assert math.isclose(result.total_dv, result.departure_dv + result.arrival_dv)
        assert result.transfer_time > 0

    def test_inward_dv_matches_outward_swapped(self) -> None:
        """Inward transfer DVs should match outward with departure/arrival swapped."""
        sanctar = _make_sanctar()
        r_inner = sanctar.radius + 20_000.0
        r_outer_sma = sanctar.radius + 80_000.0
        outward = calculate_hohmann(sanctar, 20_000.0, r_outer_sma)
        inward = calculate_hohmann(sanctar, 80_000.0, r_inner)
        assert math.isclose(inward.departure_dv, outward.arrival_dv, rel_tol=1e-9)
        assert math.isclose(inward.arrival_dv, outward.departure_dv, rel_tol=1e-9)
        assert math.isclose(inward.total_dv, outward.total_dv, rel_tol=1e-9)
        assert inward.inward is True
        assert outward.inward is False

    def test_identical_orbits_raises(self) -> None:
        """r1 == r2 should raise ValueError."""
        sanctar = _make_sanctar()
        r_same = sanctar.radius + 80_000.0
        with pytest.raises(ValueError, match="identical"):
            calculate_hohmann(sanctar, 80_000.0, r_same)

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


# ---------------------------------------------------------------------------
# Helpers for new tests
# ---------------------------------------------------------------------------


def _make_minimal_system() -> tuple[object, CelestialBody, CelestialBody]:
    """Build a minimal Sun + Home + Target system for route tests.

    Returns:
        (system, home, target) where system is a CelestialSystem.
    """
    from kopdeltav.system import CelestialSystem

    sun = CelestialBody(
        name="Sun",
        radius=261_600_000.0,
        gee_asl=28.0,
        has_ocean=False,
        atmosphere=None,
        orbit=None,
        rotational_period=432_000.0,
        display_name="Sun",
    )
    home = CelestialBody(
        name="Home",
        radius=600_000.0,
        gee_asl=1.0,
        has_ocean=False,
        atmosphere=None,
        orbit=OrbitalElements(
            semi_major_axis=13_599_840_256.0,
            eccentricity=0.0,
            inclination=0.0,
            argument_of_periapsis=0.0,
            longitude_of_ascending_node=0.0,
            mean_anomaly_at_epoch=0.0,
            epoch=0.0,
        ),
        rotational_period=21_600.0,
        display_name="Home",
        is_home_world=True,
        reference_body_name="Sun",
    )
    target = CelestialBody(
        name="Target",
        radius=320_000.0,
        gee_asl=0.9,
        has_ocean=False,
        atmosphere=None,
        orbit=OrbitalElements(
            semi_major_axis=20_726_155_264.0,
            eccentricity=0.0,
            inclination=0.0,
            argument_of_periapsis=0.0,
            longitude_of_ascending_node=0.0,
            mean_anomaly_at_epoch=0.0,
            epoch=0.0,
        ),
        rotational_period=35_000.0,
        display_name="Target",
        reference_body_name="Sun",
    )
    system: CelestialSystem = build_tree([sun, home, target])
    return system, home, target


# ---------------------------------------------------------------------------
# Tests: geostationary_altitude
# ---------------------------------------------------------------------------


class TestGeostationaryAltitude:
    def test_sanctar(self) -> None:
        """Verify formula against manual computation for Sanctar.

        Sanctar: radius=670 000 m, geeASL=1.1, rotationPeriod=90291.8154599763 s
        Expected r_geo = 10 000 000 m  →  geo_alt = 9 330 000 m
        """
        sanctar = _make_sanctar()
        alt = geostationary_altitude(sanctar)
        # Manual: r_geo = (mu * T^2 / (4*pi^2))^(1/3) - radius
        mu = sanctar.mu
        t = sanctar.rotational_period
        r_geo_expected = (mu * t * t / (4.0 * math.pi**2)) ** (1.0 / 3.0)
        expected_alt = r_geo_expected - sanctar.radius
        assert math.isclose(alt, expected_alt, rel_tol=1e-9)
        # Sanctar reference: geo_alt ≈ 9 330 000 m
        assert math.isclose(alt, 9_330_000.0, rel_tol=1e-4)

    def test_zero_rotation_raises(self) -> None:
        body = CelestialBody(
            name="Tidally",
            radius=300_000.0,
            gee_asl=0.5,
            has_ocean=False,
            atmosphere=None,
            orbit=None,
            rotational_period=0.0,
            display_name="Tidally",
        )
        with pytest.raises(ValueError, match="Rotational period must be positive"):
            geostationary_altitude(body)

    def test_negative_rotation_raises(self) -> None:
        body = CelestialBody(
            name="Retrograde",
            radius=300_000.0,
            gee_asl=0.5,
            has_ocean=False,
            atmosphere=None,
            orbit=None,
            rotational_period=-10_000.0,
            display_name="Retrograde",
        )
        with pytest.raises(ValueError, match="Rotational period must be positive"):
            geostationary_altitude(body)


# ---------------------------------------------------------------------------
# Tests: geostationary_dv
# ---------------------------------------------------------------------------


class TestGeostationaryDv:
    def test_returns_hohmann_result(self) -> None:
        """Result must be a HohmannResult with positive ΔV values."""
        from kopdeltav.calculator import HohmannResult

        sanctar = _make_sanctar()
        result = geostationary_dv(sanctar)
        assert isinstance(result, HohmannResult)
        assert result.departure_dv > 0
        assert result.arrival_dv > 0
        assert result.total_dv > 0
        assert result.transfer_time > 0

    def test_total_dv_is_sum(self) -> None:
        sanctar = _make_sanctar()
        result = geostationary_dv(sanctar)
        assert math.isclose(result.total_dv, result.departure_dv + result.arrival_dv, rel_tol=1e-9)

    def test_geo_above_low_orbit(self) -> None:
        """Geostationary orbit must be above the low orbit (sanity check)."""
        sanctar = _make_sanctar()
        lo_alt = low_orbit_altitude(sanctar)
        geo_alt = geostationary_altitude(sanctar)
        assert geo_alt > lo_alt


# ---------------------------------------------------------------------------
# Tests: escape_dv_from_low_orbit
# ---------------------------------------------------------------------------


class TestEscapeDvFromLowOrbit:
    def test_sanctar(self) -> None:
        """escape_dv must be positive and less than the surface escape velocity."""
        sanctar = _make_sanctar()
        dv = escape_dv_from_low_orbit(sanctar)
        assert dv > 0
        # At any altitude, v_escape > v_circular, so dv > 0.
        # The required ΔV from orbit must be less than escaping from the surface.
        v_esc_surface = escape_velocity(sanctar, 0.0)
        assert dv < v_esc_surface

    def test_equals_formula(self) -> None:
        """Verify dv = v_escape(lo_alt) - v_circular(lo_alt)."""
        sanctar = _make_sanctar()
        lo_alt = low_orbit_altitude(sanctar)
        expected = escape_velocity(sanctar, lo_alt) - circular_velocity(sanctar, lo_alt)
        dv = escape_dv_from_low_orbit(sanctar)
        assert math.isclose(dv, expected, rel_tol=1e-9)

    def test_airless_body(self) -> None:
        """Works for airless bodies too."""
        body = _make_airless_body()
        dv = escape_dv_from_low_orbit(body)
        assert dv > 0


# ---------------------------------------------------------------------------
# Tests: landing_dv
# ---------------------------------------------------------------------------


class TestLandingDv:
    def test_with_atmosphere(self) -> None:
        """Powered ΔV > 0; aerobrake ΔV is 0.0 (atmosphere present)."""
        sanctar = _make_sanctar()
        powered, aerobrake = landing_dv(sanctar)
        assert powered > 0
        assert aerobrake == 0.0

    def test_without_atmosphere(self) -> None:
        """Powered ΔV > 0; aerobrake is None (no atmosphere)."""
        body = _make_airless_body()
        powered, aerobrake = landing_dv(body)
        assert powered > 0
        assert aerobrake is None

    def test_powered_equals_low_orbit_velocity(self) -> None:
        """Powered ΔV equals circular velocity at low orbit altitude."""
        sanctar = _make_sanctar()
        powered, _ = landing_dv(sanctar)
        lo_alt = low_orbit_altitude(sanctar)
        v_circ = circular_velocity(sanctar, lo_alt)
        assert math.isclose(powered, v_circ, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Tests: compute_route
# ---------------------------------------------------------------------------


class TestComputeRoute:
    def test_third_cosmic_velocity(self) -> None:
        """Route with destination=None has exactly 3 steps."""
        system, _home, _target = _make_minimal_system()
        steps = compute_route(system)
        assert len(steps) == 3

    def test_route_to_planet(self) -> None:
        """Route to a planet (no moon) has exactly 5 steps."""
        system, _home, target = _make_minimal_system()
        steps = compute_route(system, destination=target)
        assert len(steps) == 5

    def test_route_steps_have_labels(self) -> None:
        """Every step must have a non-empty label."""
        system, _home, target = _make_minimal_system()
        steps = compute_route(system, destination=target)
        for step in steps:
            assert step.label, f"Step has empty label: {step}"

    def test_route_cumulative_consistency(self) -> None:
        """Cumulative value must equal running sum of individual ΔVs."""
        system, _home, target = _make_minimal_system()
        steps = compute_route(system, destination=target)
        running = 0.0
        for step in steps:
            running += step.dv
            assert math.isclose(step.cumulative, running, rel_tol=1e-9), (
                f"Cumulative mismatch at '{step.label}': "
                f"expected {running:.4f}, got {step.cumulative:.4f}"
            )

    def test_all_dvs_positive(self) -> None:
        """Every step's ΔV must be positive."""
        system, _home, target = _make_minimal_system()
        for steps in [compute_route(system), compute_route(system, destination=target)]:
            for step in steps:
                assert step.dv > 0, f"Non-positive ΔV in step '{step.label}': {step.dv}"

    def test_third_cosmic_step_labels(self) -> None:
        """Third cosmic velocity route step labels contain expected keywords."""
        system, _home, _target = _make_minimal_system()
        steps = compute_route(system)
        labels = [s.label for s in steps]
        assert any("Launch" in lbl for lbl in labels)
        assert any("Escape" in lbl for lbl in labels)

    def test_route_to_moon(self) -> None:
        """Route to a moon has exactly 6 steps and consistent cumulative ΔV."""
        system, _home, target = _make_minimal_system()
        # Add a moon to target
        moon = CelestialBody(
            name="Moon",
            radius=100_000.0,
            gee_asl=0.12,
            has_ocean=False,
            atmosphere=None,
            orbit=OrbitalElements(
                semi_major_axis=5_000_000.0,
                eccentricity=0.0,
                inclination=0.0,
                argument_of_periapsis=0.0,
                longitude_of_ascending_node=0.0,
                mean_anomaly_at_epoch=0.0,
                epoch=0.0,
            ),
            rotational_period=40_000.0,
            display_name="Moon",
            reference_body_name="Target",
        )
        moon.parent = target
        target.children.append(moon)
        system.bodies["Moon"] = moon

        steps = compute_route(system, destination=target, moon=moon)
        assert len(steps) == 6
        # Cumulative consistency
        running = 0.0
        for step in steps:
            running += step.dv
            assert math.isclose(step.cumulative, running, rel_tol=1e-9)

    def test_dvstep_dataclass(self) -> None:
        """DvStep dataclass fields are accessible and note defaults to empty."""
        step = DvStep(label="Test burn", dv=100.0, cumulative=200.0)
        assert step.label == "Test burn"
        assert step.dv == 100.0
        assert step.cumulative == 200.0
        assert step.note == ""
