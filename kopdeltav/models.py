"""Data models for celestial bodies, atmospheres, and orbital elements.

天体・大気・軌道を表現するデータ構造と補間関数。
"""

from __future__ import annotations

from dataclasses import dataclass, field

G0: float = 9.80665  # Standard gravitational acceleration [m/s²]


def compute_mu(gee_asl: float, radius: float) -> float:
    """Compute gravitational parameter mu = gee_asl * G0 * radius^2.

    重力パラメータ μ を計算する。

    Args:
        gee_asl: Surface gravity in multiples of g0.
        radius: Equatorial radius in meters.

    Returns:
        Gravitational parameter mu [m^3/s^2].
    """
    return gee_asl * G0 * radius * radius


@dataclass
class CurveKey:
    """A single keyframe of a KSP AnimationCurve.

    KSP AnimationCurve の単一キーポイント。

    Attributes:
        position: X value (e.g. altitude [m]).
        value: Y value (e.g. pressure [kPa], temperature [K]).
        in_tangent: Incoming tangent (slope per x-unit).
        out_tangent: Outgoing tangent. Defaults to in_tangent if omitted in config.
    """

    position: float
    value: float
    in_tangent: float
    out_tangent: float


@dataclass
class Atmosphere:
    """Atmospheric parameters for a celestial body.

    天体の大気パラメータ。存在すること自体が「大気あり」を意味する。
    CelestialBody.atmosphere = None は大気なし。

    Attributes:
        atmosphere_depth: Maximum altitude of atmosphere [m].
        pressure_curve: Pressure keyframes [kPa].
        temperature_curve: Temperature keyframes [K].
        molar_mass: Molar mass [kg/mol].
        adiabatic_index: Heat capacity ratio (gamma).
        pressure_at_sea_level: Sea-level pressure [kPa].
        temperature_at_sea_level: Sea-level temperature [K].
    """

    atmosphere_depth: float
    pressure_curve: list[CurveKey]
    temperature_curve: list[CurveKey]
    molar_mass: float
    adiabatic_index: float
    pressure_at_sea_level: float
    temperature_at_sea_level: float


@dataclass
class OrbitalElements:
    """Keplerian orbital elements.

    天体の軌道要素。

    Attributes:
        semi_major_axis: Semi-major axis [m].
        eccentricity: Orbital eccentricity.
        inclination: Inclination [deg].
        argument_of_periapsis: Argument of periapsis [deg].
        longitude_of_ascending_node: Longitude of ascending node [deg].
        mean_anomaly_at_epoch: Mean anomaly at epoch [deg].
        epoch: Reference epoch [s].
    """

    semi_major_axis: float
    eccentricity: float
    inclination: float
    argument_of_periapsis: float
    longitude_of_ascending_node: float
    mean_anomaly_at_epoch: float
    epoch: float


@dataclass(repr=False, eq=False)
class CelestialBody:
    """Physical and orbital parameters of a celestial body.

    天体の物理・軌道パラメータ。

    Note:
        repr=False, eq=False to prevent RecursionError from parent/children cycles.
        mu is auto-derived in __post_init__ from gee_asl * G0 * radius^2.
        soi is computed during tree construction by the parser when left at 0.

    Attributes:
        name: Internal name (e.g. "Kerbin").
        radius: Equatorial radius [m].
        gee_asl: Surface gravity [g].
        has_ocean: Whether the body has an ocean.
        atmosphere: Atmospheric data, or None if no atmosphere.
        orbit: Orbital elements, or None for the root star.
        rotational_period: Sidereal rotation period [s].
        display_name: Localized display name (falls back to name).
        soi: Sphere of influence radius [m]. 0 means needs computation.
        mu: Gravitational parameter [m^3/s^2]. Auto-derived.
        parent: Parent body. Set during tree construction.
        children: Child bodies. Set during tree construction.
    """

    name: str
    radius: float
    gee_asl: float
    has_ocean: bool
    atmosphere: Atmosphere | None
    orbit: OrbitalElements | None
    rotational_period: float
    display_name: str
    soi: float = 0.0
    mu: float = field(init=False)
    parent: CelestialBody | None = field(default=None, init=False, repr=False)
    children: list[CelestialBody] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.mu = compute_mu(self.gee_asl, self.radius)

    def __repr__(self) -> str:
        return f"CelestialBody(name={self.name!r}, radius={self.radius}, gee_asl={self.gee_asl})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CelestialBody):
            return NotImplemented
        return self.name == other.name and self.radius == other.radius

    def __hash__(self) -> int:
        return hash((self.name, self.radius))


def hermite_interp(keys: list[CurveKey], x: float) -> float:
    """Cubic Hermite Spline interpolation (KSP AnimationCurve compatible).

    KSP AnimationCurve 互換の三次エルミートスプライン補間。

    Interpolates between adjacent keyframes using cubic Hermite spline.
    Clamps to edge key values when x is outside range.
    Tangents are slopes per x-unit (not normalized).

    Args:
        keys: CurveKey list sorted ascending by position.
              Raises ValueError if empty.
        x: The position value to interpolate at.

    Returns:
        Interpolated value.

    Raises:
        ValueError: If keys is empty.
    """
    if not keys:
        raise ValueError("Cannot interpolate with empty keys list")

    if len(keys) == 1:
        return keys[0].value

    # Clamp
    if x <= keys[0].position:
        return keys[0].value
    if x >= keys[-1].position:
        return keys[-1].value

    # Find segment
    i = 0
    for j in range(1, len(keys)):
        if keys[j].position >= x:
            i = j - 1
            break

    k0 = keys[i]
    k1 = keys[i + 1]
    dx = k1.position - k0.position
    t = (x - k0.position) / dx

    # Cubic Hermite basis functions
    t2 = t * t
    t3 = t2 * t
    h00 = 2 * t3 - 3 * t2 + 1
    h10 = t3 - 2 * t2 + t
    h01 = -2 * t3 + 3 * t2
    h11 = t3 - t2

    # Tangents scaled by segment width (KSP convention)
    return h00 * k0.value + h10 * dx * k0.out_tangent + h01 * k1.value + h11 * dx * k1.in_tangent
