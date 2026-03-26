"""ΔV calculation engine for KSP celestial bodies.

天体のΔV計算エンジン。低軌道投入、ホーマン遷移、ツィオルコフスキー方程式を提供する。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from kopdeltav.models import G0, CelestialBody, hermite_interp

if TYPE_CHECKING:
    from kopdeltav.system import CelestialSystem


class SegmentType(Enum):
    """Type of a ΔV route segment, used for display coloring.

    ΔVルートセグメントの種別。表示時の色分けに使用。
    """

    LAUNCH = "launch"
    ESCAPE = "escape"
    TRANSFER = "transfer"
    CAPTURE = "capture"
    LANDING = "landing"
    SYSTEM_ESCAPE = "system_escape"
    MOON_TRANSFER = "moon_transfer"
    MOON_LANDING = "moon_landing"


# Universal gas constant [J/(mol·K)]
R_GAS: float = 8.314462618

# Earth sea-level atmospheric density [kg/m³] — reference for empirical scaling.
_EARTH_RHO_SEA_LEVEL: float = 1.225

# ---------------------------------------------------------------------------
# Empirical coefficients for launch ΔV estimation.
# Calibrated against KSP flight experience; accuracy ≈ ±10%.
# ---------------------------------------------------------------------------
_GRAVITY_LOSS_COEFF: float = 0.15  # fraction of v_orbital, scaled by gee_asl
_DRAG_LOSS_COEFF: float = 0.05  # fraction of v_orbital, scaled by rho/rho_earth
_JET_SAVINGS_COEFF: float = 0.44  # fraction of v_orbital saved by jet engines


# ---------------------------------------------------------------------------
# Orbital mechanics
# ---------------------------------------------------------------------------


def low_orbit_altitude(body: CelestialBody) -> float:
    """Estimate a reasonable low orbit altitude for the body.

    天体の妥当な低軌道高度を推定する。

    For bodies with atmosphere, returns approximately 10% above the atmosphere
    depth to ensure a stable orbit well outside the atmosphere.  For airless
    bodies, returns 5% of the body radius (minimum 10 000 m).

    Args:
        body: Target celestial body.

    Returns:
        Estimated low orbit altitude above surface [m].
    """
    if body.atmosphere is not None:
        return body.atmosphere.atmosphere_depth * 1.1
    return max(body.radius * 0.05, 10_000.0)


def circular_velocity(body: CelestialBody, altitude: float) -> float:
    """Circular orbital velocity at given altitude above surface.

    指定高度での円軌道速度を計算する。

    Uses v_circular = √(μ / r) where r = radius + altitude.

    Args:
        body: Target celestial body.
        altitude: Altitude above surface [m].

    Returns:
        Orbital velocity [m/s].

    Raises:
        ValueError: If altitude is negative.
    """
    if altitude < 0:
        raise ValueError(f"Altitude must be non-negative: {altitude}")
    r = body.radius + altitude
    return math.sqrt(body.mu / r)


def escape_velocity(body: CelestialBody, altitude: float) -> float:
    """Escape velocity at given altitude above surface.

    指定高度での脱出速度を計算する。

    Uses v_escape = sqrt(2 * mu / r) = sqrt(2) * v_circular at the same altitude.

    Args:
        body: Target celestial body.
        altitude: Altitude above surface [m].

    Returns:
        Escape velocity [m/s].

    Raises:
        ValueError: If altitude is negative.
    """
    if altitude < 0:
        raise ValueError(f"Altitude must be non-negative: {altitude}")
    r = body.radius + altitude
    return math.sqrt(2.0 * body.mu / r)


# ---------------------------------------------------------------------------
# Atmospheric density
# ---------------------------------------------------------------------------


def density_at_altitude(body: CelestialBody, altitude: float) -> float | None:
    """Calculate atmospheric density at altitude using hermite-interpolated curves.

    高度ごとの大気密度をエルミート補間カーブで計算する。

    Applies the ideal gas law rho = P * M / (R_gas * T) where pressure and
    temperature are obtained from the body's atmosphere curves via cubic
    Hermite spline interpolation.  When curves are empty, falls back to
    sea-level scalar values (meaningful only at altitude 0).

    **Important**: Pressure in the curves is in kPa; it must be converted to
    Pa (x1000) before applying the ideal gas law.

    Args:
        body: Target celestial body.
        altitude: Altitude above surface [m].

    Returns:
        Atmospheric density [kg/m³], or ``None`` if the body has no
        atmosphere.  Returns ``0.0`` for altitudes at or above the
        atmosphere depth.
    """
    if body.atmosphere is None:
        return None

    atmo = body.atmosphere

    if altitude >= atmo.atmosphere_depth:
        return 0.0

    # Pressure [kPa] from curve, falling back to sea-level scalar.
    if atmo.pressure_curve:
        pressure_kpa = hermite_interp(atmo.pressure_curve, altitude)
    else:
        pressure_kpa = atmo.pressure_at_sea_level if altitude == 0.0 else 0.0

    # Temperature [K] from curve, falling back to sea-level scalar.
    if atmo.temperature_curve:
        temperature_k = hermite_interp(atmo.temperature_curve, altitude)
    else:
        temperature_k = atmo.temperature_at_sea_level if altitude == 0.0 else 0.0

    if temperature_k <= 0.0 or pressure_kpa <= 0.0:
        return 0.0

    # kPa → Pa conversion, then ideal gas law.
    pressure_pa = pressure_kpa * 1000.0
    return pressure_pa * atmo.molar_mass / (R_GAS * temperature_k)


def surface_density(body: CelestialBody) -> float | None:
    """Calculate sea-level atmospheric density using the ideal gas law.

    海面大気密度を理想気体の式で計算する。大気なしの場合は None。

    Delegates to :func:`density_at_altitude` at altitude 0, which evaluates
    the pressure and temperature curves at sea level.  This correctly
    accounts for curve-based sea-level temperature that may differ from the
    ``temperatureSeaLevel`` scalar.

    Args:
        body: Target celestial body.

    Returns:
        Sea-level atmospheric density [kg/m³], or ``None`` if no atmosphere.
    """
    return density_at_altitude(body, 0.0)


# ---------------------------------------------------------------------------
# Launch ΔV
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LaunchResult:
    """Results of a launch-to-orbit ΔV calculation.

    低軌道投入ΔV計算の結果。

    Attributes:
        orbital_velocity: Circular velocity at target orbit [m/s].
        gravity_loss: Estimated gravity loss [m/s].
        drag_loss: Estimated atmospheric drag loss [m/s].
        total_ideal: Theoretical minimum (= orbital velocity) [m/s].
        total_rocket: Practical rocket ΔV with losses [m/s].
        jet_savings: ΔV saved if using jet engines in lower atmosphere [m/s].
        total_with_jets: total_rocket - jet_savings [m/s].
    """

    orbital_velocity: float
    gravity_loss: float
    drag_loss: float
    total_ideal: float
    total_rocket: float
    jet_savings: float
    total_with_jets: float


def calculate_launch(body: CelestialBody, target_altitude: float) -> LaunchResult:
    """Calculate launch-to-orbit ΔV for a body.

    天体の低軌道投入ΔVを計算する。

    This is an **empirical** model.  All loss and savings values are rough
    approximations calibrated against KSP flight data.  Estimated accuracy
    is ±10 % for *total_rocket* and ±15 % for *jet_savings*.  Actual values
    depend heavily on vehicle design, thrust-to-weight ratio, and ascent
    profile.

    Assumptions:
        - **Gravity loss** ≈ 15 % of orbital velocity, scaled linearly by the
          body's surface gravity (gee_asl).  Higher gravity → longer burn →
          more gravity drag.
        - **Drag loss** ≈ 5 % of orbital velocity, scaled by the ratio of sea-
          level density to Earth's reference density (1.225 kg/m³).  Zero for
          airless bodies.
        - **Jet savings** ≈ 44 % of orbital velocity, representing the
          efficiency gain of air-breathing engines in the lower atmosphere.
          Capped when the density ratio rho/rho_Earth exceeds 1.0 (above Earth-
          like density, engine performance plateaus).  Zero for airless bodies.

    Args:
        body: Target celestial body.
        target_altitude: Target circular orbit altitude above surface [m].

    Returns:
        :class:`LaunchResult` with computed ΔV values.

    Raises:
        ValueError: If *target_altitude* is negative.
    """
    if target_altitude < 0:
        raise ValueError(f"Target altitude must be non-negative: {target_altitude}")

    v_orbital = circular_velocity(body, target_altitude)

    # Gravity loss: scales with surface gravity.
    gravity_loss = v_orbital * _GRAVITY_LOSS_COEFF * body.gee_asl

    # Drag loss: scales with atmospheric density relative to Earth.
    rho = surface_density(body)
    if rho is not None and rho > 0.0:
        drag_loss = v_orbital * _DRAG_LOSS_COEFF * (rho / _EARTH_RHO_SEA_LEVEL)
    else:
        drag_loss = 0.0

    total_ideal = v_orbital
    total_rocket = v_orbital + gravity_loss + drag_loss

    # Jet savings: only possible with atmosphere; capped at density ratio 1.0.
    if rho is not None and rho > 0.0:
        density_factor = min(rho / _EARTH_RHO_SEA_LEVEL, 1.0)
        jet_savings = v_orbital * _JET_SAVINGS_COEFF * density_factor
    else:
        jet_savings = 0.0

    total_with_jets = total_rocket - jet_savings

    return LaunchResult(
        orbital_velocity=v_orbital,
        gravity_loss=gravity_loss,
        drag_loss=drag_loss,
        total_ideal=total_ideal,
        total_rocket=total_rocket,
        jet_savings=jet_savings,
        total_with_jets=total_with_jets,
    )


# ---------------------------------------------------------------------------
# Hohmann transfer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HohmannResult:
    """Results of a Hohmann transfer calculation.

    ホーマン遷移計算の結果。

    Attributes:
        departure_dv: ΔV for departure burn [m/s].
        arrival_dv: ΔV for arrival/capture burn [m/s].
        total_dv: Total ΔV (departure + arrival) [m/s].
        transfer_time: Transfer time (half-period of the transfer ellipse) [s].
        inward: True if the transfer is to an inner (lower) orbit.
    """

    departure_dv: float
    arrival_dv: float
    total_dv: float
    transfer_time: float
    inward: bool = False


def calculate_hohmann(
    body: CelestialBody,
    parking_altitude: float,
    target_sma: float,
) -> HohmannResult:
    """Calculate Hohmann transfer from parking orbit to target orbit.

    パーキング軌道からターゲット軌道へのホーマン遷移ΔVを計算する。

    Supports both outward (target > parking) and inward (target < parking)
    transfers.  For inward transfers the vis-viva computation uses the
    swapped radii internally and the returned departure/arrival ΔVs are
    swapped so that ``departure_dv`` is the burn at the parking orbit and
    ``arrival_dv`` is the burn at the target orbit.

    Standard Hohmann transfer equations (outward case)::

        a_transfer = (r1 + r2) / 2
        v_transfer_peri = sqrt(mu * (2/r1 - 1/a_transfer))
        departure_dv = v_transfer_peri - v_circular(r1)
        v_transfer_apo  = sqrt(mu * (2/r2 - 1/a_transfer))
        arrival_dv = v_circular(r2) - v_transfer_apo
        transfer_time = pi * sqrt(a_transfer**3 / mu)

    Args:
        body: Central body being orbited.
        parking_altitude: Altitude of circular parking orbit above surface [m].
        target_sma: Semi-major axis of target orbit [m] (from body center).

    Returns:
        :class:`HohmannResult` with ΔV and transfer time values.

    Raises:
        ValueError: If *parking_altitude* is negative or parking orbit radius
            and *target_sma* are identical (zero-ΔV transfer).
    """
    if parking_altitude < 0:
        raise ValueError(f"Parking altitude must be non-negative: {parking_altitude}")

    r_parking = body.radius + parking_altitude
    r_target = target_sma

    if math.isclose(r_parking, r_target, rel_tol=1e-12):
        raise ValueError(
            f"Parking orbit radius ({r_parking} m) and target SMA ({r_target} m) "
            "are identical; Hohmann transfer is undefined"
        )

    inward = r_target < r_parking

    # For vis-viva, r_inner is the periapsis and r_outer is the apoapsis.
    r_inner = min(r_parking, r_target)
    r_outer = max(r_parking, r_target)

    mu = body.mu
    a_transfer = (r_inner + r_outer) / 2.0

    # Burn at periapsis of the transfer ellipse.
    v_inner_circular = math.sqrt(mu / r_inner)
    v_transfer_peri = math.sqrt(mu * (2.0 / r_inner - 1.0 / a_transfer))
    dv_peri = v_transfer_peri - v_inner_circular

    # Burn at apoapsis of the transfer ellipse.
    v_outer_circular = math.sqrt(mu / r_outer)
    v_transfer_apo = math.sqrt(mu * (2.0 / r_outer - 1.0 / a_transfer))
    dv_apo = v_outer_circular - v_transfer_apo

    # Transfer time: half the period of the transfer ellipse.
    transfer_time = math.pi * math.sqrt(a_transfer**3 / mu)

    if inward:
        # Inward: departure is at the outer (parking) orbit, arrival at inner.
        departure_dv = dv_apo
        arrival_dv = dv_peri
    else:
        # Outward: departure is at the inner (parking) orbit, arrival at outer.
        departure_dv = dv_peri
        arrival_dv = dv_apo

    return HohmannResult(
        departure_dv=departure_dv,
        arrival_dv=arrival_dv,
        total_dv=departure_dv + arrival_dv,
        transfer_time=transfer_time,
        inward=inward,
    )


# ---------------------------------------------------------------------------
# Tsiolkovsky rocket equation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TsiolkovskyResult:
    """Results of the Tsiolkovsky rocket equation.

    ツィオルコフスキーの式の計算結果。

    Attributes:
        mass_ratio: Wet mass / dry mass ratio.
        fuel_fraction: Fraction of total mass that is fuel (1 - 1/mass_ratio).
        dry_mass: Dry (empty) mass [kg].
        fuel_mass: Fuel mass [kg].
    """

    mass_ratio: float
    fuel_fraction: float
    dry_mass: float
    fuel_mass: float


def calculate_tsiolkovsky(
    delta_v: float,
    isp: float,
    wet_mass: float,
) -> TsiolkovskyResult:
    """Apply the Tsiolkovsky rocket equation.

    ツィオルコフスキーの式を適用して質量比を計算する。

    dv = Isp * g0 * ln(m_wet / m_dry)
    mass_ratio = exp(dv / (Isp * g0))

    Args:
        delta_v: Required ΔV [m/s].
        isp: Specific impulse [s].
        wet_mass: Total (wet) mass [kg].

    Returns:
        :class:`TsiolkovskyResult` with mass ratio and fuel breakdown.

    Raises:
        ValueError: If *delta_v* is negative, *isp* is non-positive, or
            *wet_mass* is non-positive.
    """
    if delta_v < 0:
        raise ValueError(f"delta_v must be non-negative: {delta_v}")
    if isp <= 0:
        raise ValueError(f"Isp must be positive: {isp}")
    if wet_mass <= 0:
        raise ValueError(f"wet_mass must be positive: {wet_mass}")

    ve = isp * G0  # effective exhaust velocity [m/s]
    mass_ratio = math.exp(delta_v / ve)
    fuel_fraction = 1.0 - 1.0 / mass_ratio
    dry_mass = wet_mass / mass_ratio
    fuel_mass = wet_mass - dry_mass

    return TsiolkovskyResult(
        mass_ratio=mass_ratio,
        fuel_fraction=fuel_fraction,
        dry_mass=dry_mass,
        fuel_mass=fuel_mass,
    )


# ---------------------------------------------------------------------------
# Geostationary orbit
# ---------------------------------------------------------------------------


def geostationary_altitude(body: CelestialBody) -> float:
    """Calculate the altitude of a geostationary orbit.

    静止軌道の高度を計算する。

    Uses the formula::

        r_geo = (mu * T^2 / (4 * pi^2))^(1/3)
        altitude = r_geo - radius

    where *T* is the sidereal rotation period of the body.

    Args:
        body: Target celestial body.

    Returns:
        Geostationary orbit altitude above surface [m].

    Raises:
        ValueError: If ``body.rotational_period`` is non-positive.
    """
    if body.rotational_period <= 0.0:
        raise ValueError(
            f"Rotational period must be positive for a geostationary orbit: "
            f"{body.rotational_period}"
        )
    t = body.rotational_period
    r_geo: float = math.pow(body.mu * t * t / (4.0 * math.pi**2), 1.0 / 3.0)
    return r_geo - body.radius


def geostationary_dv(body: CelestialBody) -> HohmannResult:
    """Calculate the ΔV for a Hohmann transfer from low orbit to geostationary orbit.

    低軌道から静止軌道へのホーマン遷移ΔVを計算する。

    Args:
        body: Target celestial body.

    Returns:
        :class:`HohmannResult` for the low orbit → geostationary transfer.

    Raises:
        ValueError: If ``body.rotational_period`` is non-positive, or if the
            geostationary orbit is below the low orbit (extremely fast rotators).
    """
    lo_alt = low_orbit_altitude(body)
    geo_alt = geostationary_altitude(body)
    geo_sma = body.radius + geo_alt
    return calculate_hohmann(body, lo_alt, geo_sma)


# ---------------------------------------------------------------------------
# Escape ΔV from low orbit
# ---------------------------------------------------------------------------


def escape_dv_from_low_orbit(body: CelestialBody) -> float:
    """Calculate the ΔV needed to escape from low orbit.

    低軌道から脱出するのに必要なΔVを計算する。

    Computes ``v_escape(lo_alt) - v_circular(lo_alt)``, which is the
    impulsive burn required to reach escape velocity from a circular
    parking orbit at the standard low orbit altitude.

    Args:
        body: Target celestial body.

    Returns:
        Escape ΔV from low orbit [m/s]. Always positive.
    """
    lo_alt = low_orbit_altitude(body)
    v_esc = escape_velocity(body, lo_alt)
    v_circ = circular_velocity(body, lo_alt)
    return v_esc - v_circ


# ---------------------------------------------------------------------------
# Landing ΔV
# ---------------------------------------------------------------------------


def landing_dv(body: CelestialBody) -> tuple[float, float | None]:
    """Estimate the ΔV required to land on a body.

    天体への着陸に必要なΔVを推定する。

    The powered landing ΔV is approximated as the circular orbital velocity
    at the low orbit altitude — representing the speed that must be cancelled
    to descend from orbit to the surface.

    For bodies **with** atmosphere, aerobraking can absorb most of the
    orbital energy; the aerobrake contribution is returned as ``0.0`` (the
    rocket engine burn during atmospheric descent is negligible compared to
    the powered case).  The caller can display this as "aerobrake assist."

    For bodies **without** atmosphere, there is no aerobraking option, so
    the second element is ``None``.

    Args:
        body: Target celestial body.

    Returns:
        A tuple ``(powered_dv, aerobrake_dv)`` where:

        - *powered_dv*: ΔV for a fully powered landing [m/s]. Always > 0.
        - *aerobrake_dv*: ``0.0`` if the body has atmosphere (aerobraking
          handles orbital deceleration); ``None`` if no atmosphere.
    """
    lo_alt = low_orbit_altitude(body)
    powered_dv = circular_velocity(body, lo_alt)
    aerobrake_dv: float | None = 0.0 if body.atmosphere is not None else None
    return powered_dv, aerobrake_dv


# ---------------------------------------------------------------------------
# ΔV route planner
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DvStep:
    """A single step in a ΔV route.

    ΔVルートの1ステップ。

    Attributes:
        label: Human-readable description of this maneuver.
        dv: ΔV for this step [m/s].
        cumulative: Running total ΔV from mission start [m/s].
        segment_type: Type of maneuver for display purposes.
        note: Optional supplementary information (e.g. aerobrake alternative).
    """

    label: str
    dv: float
    cumulative: float
    segment_type: SegmentType = SegmentType.TRANSFER
    note: str = ""


def compute_route(
    system: CelestialSystem,
    destination: CelestialBody | None = None,
    moon: CelestialBody | None = None,
) -> list[DvStep]:
    """Compute a ΔV route from the home world to an optional destination.

    ホームワールドから目的地までのΔVルートを計算する。

    Three modes depending on the arguments:

    **Third cosmic velocity** (``destination=None``):
        1. Launch to low orbit (total_rocket from :func:`calculate_launch`).
        2. Escape home world (:func:`escape_dv_from_low_orbit`).
        3. Escape star system: Hohmann-style burn at the home world's orbital
           altitude around the parent star (``v_escape - v_circular`` at that
           altitude in the parent's gravity).

    **Planet flyby / capture** (``destination=planet``, ``moon=None``):
        1. Launch to low orbit.
        2. Escape home world.
        3. Hohmann transfer in parent body's frame (home SMA → destination SMA).
        4. Destination orbit insertion (≈ ``escape_dv_from_low_orbit`` of
           destination — reverse capture burn).
        5. Landing on destination.

    **Moon mission** (``destination=planet``, ``moon=satellite``):
        Steps 1-4 as above.
        5. Hohmann transfer from destination low orbit to moon SMA.
        6. Landing on moon.

    All intermediate values are accumulated into the ``cumulative`` field of
    each :class:`DvStep`.

    Args:
        system: The :class:`~kopdeltav.system.CelestialSystem` describing the
            planetary system.
        destination: Target planet (must orbit the same parent as the home
            world).  Pass ``None`` to compute the third cosmic velocity route.
        moon: Target moon orbiting *destination*.  Ignored when
            ``destination`` is ``None``.

    Returns:
        Ordered list of :class:`DvStep` objects representing each maneuver.

    Raises:
        ValueError: If the home world has no orbit (root star) or no parent,
            or if *destination* / *moon* have no orbit data.
    """
    home = system.home_world
    parent = home.parent
    if parent is None:
        raise ValueError(
            f"Home world '{home.name}' has no parent body; cannot compute interplanetary route."
        )
    if home.orbit is None:
        raise ValueError(
            f"Home world '{home.name}' has no orbital elements; "
            "cannot compute interplanetary route."
        )

    steps: list[DvStep] = []
    cumulative = 0.0

    def _add(
        label: str,
        dv: float,
        seg_type: SegmentType = SegmentType.TRANSFER,
        note: str = "",
    ) -> None:
        nonlocal cumulative
        cumulative += dv
        steps.append(
            DvStep(
                label=label,
                dv=dv,
                cumulative=cumulative,
                segment_type=seg_type,
                note=note,
            )
        )

    # Step 1: Launch to low orbit.
    lo_alt = low_orbit_altitude(home)
    launch = calculate_launch(home, lo_alt)
    _add("Launch to low orbit", launch.total_rocket, SegmentType.LAUNCH)

    # Step 2: Escape home world.
    esc_home = escape_dv_from_low_orbit(home)
    _add(f"Escape {home.name}", esc_home, SegmentType.ESCAPE)

    if destination is None:
        # Third cosmic velocity: escape the parent star system from home orbit.
        home_sma = home.orbit.semi_major_axis
        home_orbit_alt = home_sma - parent.radius
        v_esc_star = escape_velocity(parent, home_orbit_alt)
        v_circ_star = circular_velocity(parent, home_orbit_alt)
        esc_star = v_esc_star - v_circ_star
        _add(f"Escape {parent.name} system", esc_star, SegmentType.SYSTEM_ESCAPE)
        return steps

    # destination is set — interplanetary mission.
    if destination.orbit is None:
        raise ValueError(f"Destination '{destination.name}' has no orbital elements.")

    # Step 3: Hohmann transfer in parent's frame.
    home_sma = home.orbit.semi_major_axis
    home_orbit_alt = home_sma - parent.radius
    dest_sma = destination.orbit.semi_major_axis
    hohmann = calculate_hohmann(parent, home_orbit_alt, dest_sma)
    _add(f"Transfer to {destination.name}", hohmann.departure_dv, SegmentType.TRANSFER)

    # Step 4: Capture at destination.
    esc_dest = escape_dv_from_low_orbit(destination)
    _add(f"Capture at {destination.name}", esc_dest, SegmentType.CAPTURE)

    if moon is None:
        # Step 5: Land on destination.
        powered_dv, aerobrake_dv = landing_dv(destination)
        note = f"aerobrake option: {aerobrake_dv} m/s" if aerobrake_dv is not None else ""
        _add(f"Land on {destination.name}", powered_dv, SegmentType.LANDING, note=note)
        return steps

    # Moon mission.
    if moon.orbit is None:
        raise ValueError(f"Moon '{moon.name}' has no orbital elements.")

    # Step 5: Transfer from destination low orbit to moon SMA.
    dest_lo_alt = low_orbit_altitude(destination)
    moon_sma = moon.orbit.semi_major_axis
    moon_hohmann = calculate_hohmann(destination, dest_lo_alt, moon_sma)
    _add(f"Transfer to {moon.name}", moon_hohmann.departure_dv, SegmentType.MOON_TRANSFER)

    # Step 6: Land on moon.
    powered_dv_moon, aerobrake_dv_moon = landing_dv(moon)
    note_moon = (
        f"aerobrake option: {aerobrake_dv_moon} m/s" if aerobrake_dv_moon is not None else ""
    )
    _add(f"Land on {moon.name}", powered_dv_moon, SegmentType.MOON_LANDING, note=note_moon)

    return steps
