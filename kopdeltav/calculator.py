"""ΔV calculation engine for KSP celestial bodies.

天体のΔV計算エンジン。低軌道投入、ホーマン遷移、ツィオルコフスキー方程式を提供する。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from kopdeltav.models import G0, CelestialBody, hermite_interp

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


@dataclass
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


@dataclass
class HohmannResult:
    """Results of a Hohmann transfer calculation.

    ホーマン遷移計算の結果。

    Attributes:
        departure_dv: ΔV for departure burn [m/s].
        arrival_dv: ΔV for arrival/capture burn [m/s].
        total_dv: Total ΔV (departure + arrival) [m/s].
        transfer_time: Transfer time (half-period of the transfer ellipse) [s].
    """

    departure_dv: float
    arrival_dv: float
    total_dv: float
    transfer_time: float


def calculate_hohmann(
    body: CelestialBody,
    parking_altitude: float,
    target_sma: float,
) -> HohmannResult:
    """Calculate Hohmann transfer from parking orbit to target orbit.

    パーキング軌道からターゲット軌道へのホーマン遷移ΔVを計算する。

    Standard Hohmann transfer equations::

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
        ValueError: If *parking_altitude* is negative or *target_sma* is not
            larger than the parking orbit radius.
    """
    if parking_altitude < 0:
        raise ValueError(f"Parking altitude must be non-negative: {parking_altitude}")

    r1 = body.radius + parking_altitude
    r2 = target_sma

    if r2 <= r1:
        raise ValueError(f"Target SMA ({r2} m) must be larger than parking orbit radius ({r1} m)")

    mu = body.mu
    a_transfer = (r1 + r2) / 2.0

    # Departure burn (periapsis of transfer ellipse).
    v1_circular = math.sqrt(mu / r1)
    v_transfer_peri = math.sqrt(mu * (2.0 / r1 - 1.0 / a_transfer))
    departure_dv = v_transfer_peri - v1_circular

    # Arrival burn (apoapsis of transfer ellipse).
    v2_circular = math.sqrt(mu / r2)
    v_transfer_apo = math.sqrt(mu * (2.0 / r2 - 1.0 / a_transfer))
    arrival_dv = v2_circular - v_transfer_apo

    # Transfer time: half the period of the transfer ellipse.
    transfer_time = math.pi * math.sqrt(a_transfer**3 / mu)

    return HohmannResult(
        departure_dv=departure_dv,
        arrival_dv=arrival_dv,
        total_dv=departure_dv + arrival_dv,
        transfer_time=transfer_time,
    )


# ---------------------------------------------------------------------------
# Tsiolkovsky rocket equation
# ---------------------------------------------------------------------------


@dataclass
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
