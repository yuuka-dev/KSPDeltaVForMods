# CLI ΔV Map & Engine Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix inner-planet and sub-star-system ΔV routing, add CLI i18n (ja/en/id), subway-map route display, detail view, output formats, and project scaffolding (README, LICENSE, CHANGELOG, CI, release).

**Architecture:** Core-first approach. Fix `calculate_hohmann` to handle inward transfers, then layer i18n on top of all CLI output, then build the subway-map display and output formatters. Docs and CI run in parallel via worktrees.

**Tech Stack:** Python 3.10+ (stdlib only for `kopdeltav/`), pytest, ruff, mypy, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-03-26-cli-deltav-map-design.md`

---

## File Map

| File | Responsibility | Task |
|------|---------------|------|
| `kopdeltav/calculator.py` | HohmannResult frozen+inward, SegmentType enum, DvStep frozen+typed, compute_route inner/sub-system | 1, 2 |
| `kopdeltav/system.py` | sort_by_transfer_dv simplification (after calc fix), is_barycenter heuristic | 1, 2 |
| `kopdeltav/i18n.py` | Indonesian translations, detect_language(), key safety | 3 |
| `run.py` | --lang flag, i18n integration, subway-map renderer, detail view, --format, SIGPIPE, ANSI/Unicode detection, barycenter forced selection | 3, 4, 5 |
| `tests/test_calculator.py` | Inward Hohmann, frozen dataclass, inner route, sub-system route tests | 1, 2 |
| `tests/test_i18n.py` | Indonesian keys, detect_language, key fallback tests | 3 |
| `tests/test_display.py` (new) | Subway-map output, ANSI detection, format output, snapshot tests | 5 |
| `README.md` (new) | English main README | 6 |
| `README-ja.md` (new) | Japanese README | 6 |
| `README-id.md` (new) | Indonesian README | 6 |
| `LICENSE` (new) | MIT license | 6 |
| `CHANGELOG.md` (new) | Keep a Changelog | 6 |
| `.github/workflows/ci.yml` (new) | Lint + type-check + test | 7 |

---

## Task 1: Inner Planet Hohmann Transfer Fix

**Branch:** `dev/fix/inner-planet-hohmann`
**Issue:** #1

**Files:**
- Modify: `kopdeltav/calculator.py:283-362` (HohmannResult + calculate_hohmann)
- Modify: `kopdeltav/system.py:253-277` (sort_by_transfer_dv simplification)
- Modify: `tests/test_calculator.py:241-303` (TestCalculateHohmann)

- [ ] **Step 1: Write failing test for inward Hohmann transfer**

Add to `tests/test_calculator.py` in `TestCalculateHohmann`:

```python
def test_inward_transfer(self) -> None:
    """Hohmann transfer to inner orbit (r2 < r1) must work and set inward=True."""
    sanctar = _make_sanctar()
    # Target SMA inside parking orbit
    r_inner = sanctar.radius + 20_000.0  # 20 km altitude (below 80 km parking)
    result = calculate_hohmann(sanctar, 80_000.0, r_inner)
    assert result.inward is True
    assert result.departure_dv > 0
    assert result.arrival_dv > 0
    assert math.isclose(result.total_dv, result.departure_dv + result.arrival_dv)
    assert result.transfer_time > 0

def test_inward_dv_matches_outward_swapped(self) -> None:
    """Inward transfer ΔVs should match outward with departure/arrival swapped."""
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

def test_equal_orbits_raises(self) -> None:
    """r1 == r2 should raise ValueError."""
    sanctar = _make_sanctar()
    r_same = sanctar.radius + 80_000.0
    with pytest.raises(ValueError, match="identical"):
        calculate_hohmann(sanctar, 80_000.0, r_same)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_calculator.py::TestCalculateHohmann::test_inward_transfer tests/test_calculator.py::TestCalculateHohmann::test_inward_dv_matches_outward_swapped tests/test_calculator.py::TestCalculateHohmann::test_equal_orbits_raises -v`
Expected: FAIL (AttributeError: 'HohmannResult' has no attribute 'inward', and ValueError for inward case)

- [ ] **Step 3: Add `inward` field to HohmannResult and make it frozen**

In `kopdeltav/calculator.py`, replace the HohmannResult dataclass:

```python
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
```

- [ ] **Step 4: Modify calculate_hohmann to handle r2 < r1**

Replace the validation and computation in `calculate_hohmann`:

```python
def calculate_hohmann(
    body: CelestialBody,
    parking_altitude: float,
    target_sma: float,
) -> HohmannResult:
    """Calculate Hohmann transfer from parking orbit to target orbit.

    パーキング軌道からターゲット軌道へのホーマン遷移ΔVを計算する。

    Supports both outward (target > parking) and inward (target < parking)
    transfers.  For inward transfers, the departure and arrival ΔVs are
    swapped so that ``departure_dv`` always represents the first burn and
    ``arrival_dv`` the circularization burn at the destination.

    Args:
        body: Central body being orbited.
        parking_altitude: Altitude of circular parking orbit above surface [m].
        target_sma: Semi-major axis of target orbit [m] (from body center).

    Returns:
        :class:`HohmannResult` with ΔV and transfer time values.

    Raises:
        ValueError: If *parking_altitude* is negative or parking orbit and
            target orbit are identical.
    """
    if parking_altitude < 0:
        raise ValueError(f"Parking altitude must be non-negative: {parking_altitude}")

    r_parking = body.radius + parking_altitude
    r_target = target_sma

    if math.isclose(r_parking, r_target, rel_tol=1e-9):
        raise ValueError(
            f"Parking orbit ({r_parking} m) and target orbit ({r_target} m) are identical"
        )

    inward = r_target < r_parking
    r1 = min(r_parking, r_target)
    r2 = max(r_parking, r_target)

    mu = body.mu
    a_transfer = (r1 + r2) / 2.0

    # Departure burn (periapsis of transfer ellipse).
    v1_circular = math.sqrt(mu / r1)
    v_transfer_peri = math.sqrt(mu * (2.0 / r1 - 1.0 / a_transfer))
    dv_peri = v_transfer_peri - v1_circular

    # Arrival burn (apoapsis of transfer ellipse).
    v2_circular = math.sqrt(mu / r2)
    v_transfer_apo = math.sqrt(mu * (2.0 / r2 - 1.0 / a_transfer))
    dv_apo = v2_circular - v_transfer_apo

    # Transfer time: half the period of the transfer ellipse.
    transfer_time = math.pi * math.sqrt(a_transfer**3 / mu)

    # For inward transfers, the spacecraft starts at r2 (outer/higher orbit)
    # and arrives at r1 (inner/lower orbit), so swap departure/arrival.
    if inward:
        departure_dv, arrival_dv = dv_apo, dv_peri
    else:
        departure_dv, arrival_dv = dv_peri, dv_apo

    return HohmannResult(
        departure_dv=departure_dv,
        arrival_dv=arrival_dv,
        total_dv=departure_dv + arrival_dv,
        transfer_time=transfer_time,
        inward=inward,
    )
```

- [ ] **Step 5: Update existing test that checks for "larger" error**

In `tests/test_calculator.py`, replace `test_target_below_parking_raises`:

```python
def test_identical_orbits_raises(self) -> None:
    """Identical parking and target orbits should raise ValueError."""
    sanctar = _make_sanctar()
    r_same = sanctar.radius + 80_000.0
    with pytest.raises(ValueError, match="identical"):
        calculate_hohmann(sanctar, 80_000.0, r_same)
```

Remove the old `test_target_below_parking_raises` test.

- [ ] **Step 6: Run all Hohmann tests**

Run: `pytest tests/test_calculator.py::TestCalculateHohmann -v`
Expected: ALL PASS

- [ ] **Step 7: Simplify sort_by_transfer_dv**

In `kopdeltav/system.py`, the manual min/max swap is no longer needed since `calculate_hohmann` handles inward transfers. Replace lines 264-269:

```python
        target_sma = target.orbit.semi_major_axis
        try:
            origin_sma = origin.orbit.semi_major_axis
            origin_alt = origin_sma - parent.radius
            hohmann = calculate_hohmann(parent, origin_alt, target_sma)
        except ValueError as exc:
```

- [ ] **Step 8: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 9: Run linters**

Run: `ruff check kopdeltav/ tests/ && ruff format --check kopdeltav/ tests/`
Expected: No errors. If format issues, run `ruff format kopdeltav/ tests/`.

- [ ] **Step 10: Commit**

```bash
git add kopdeltav/calculator.py kopdeltav/system.py tests/test_calculator.py
git commit -m "fix(calculator): support inward Hohmann transfers (r2 < r1)

calculate_hohmann now handles inner planet transfers by swapping r1/r2
internally and returning swapped departure/arrival ΔVs. HohmannResult
gains frozen=True and inward field. sort_by_transfer_dv simplified."
```

---

## Task 2: Sub-Star-System Routing & Barycenter Detection

**Branch:** `dev/fix/inner-planet-hohmann` (same branch as Task 1)
**Issue:** #1

**Files:**
- Modify: `kopdeltav/calculator.py:560-577` (DvStep frozen + SegmentType enum)
- Modify: `kopdeltav/calculator.py:579-739` (compute_route inner planet fix)
- Modify: `kopdeltav/system.py` (add is_barycenter helper)
- Modify: `run.py:340-370` (force sub-body selection for barycenters)
- Modify: `tests/test_calculator.py:351-648` (new route tests)

- [ ] **Step 1: Add SegmentType enum and update DvStep**

In `kopdeltav/calculator.py`, add after the imports and before `low_orbit_altitude`:

```python
from enum import Enum


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
```

Update DvStep:

```python
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
```

- [ ] **Step 2: Write failing tests for inner planet route and sub-system route**

Add to `tests/test_calculator.py`:

```python
def _make_system_with_inner_planet():
    """Build Sun + Home + InnerPlanet system where InnerPlanet SMA < Home SMA."""
    from kopdeltav.system import CelestialSystem

    sun = CelestialBody(
        name="Sun", radius=261_600_000.0, gee_asl=28.0, has_ocean=False,
        atmosphere=None, orbit=None, rotational_period=432_000.0, display_name="Sun",
    )
    home = CelestialBody(
        name="Home", radius=600_000.0, gee_asl=1.0, has_ocean=False,
        atmosphere=None,
        orbit=OrbitalElements(
            semi_major_axis=13_599_840_256.0, eccentricity=0.0, inclination=0.0,
            argument_of_periapsis=0.0, longitude_of_ascending_node=0.0,
            mean_anomaly_at_epoch=0.0, epoch=0.0,
        ),
        rotational_period=21_600.0, display_name="Home", is_home_world=True,
        reference_body_name="Sun",
    )
    inner = CelestialBody(
        name="Inner", radius=300_000.0, gee_asl=0.8, has_ocean=False,
        atmosphere=None,
        orbit=OrbitalElements(
            semi_major_axis=5_263_138_304.0, eccentricity=0.0, inclination=0.0,
            argument_of_periapsis=0.0, longitude_of_ascending_node=0.0,
            mean_anomaly_at_epoch=0.0, epoch=0.0,
        ),
        rotational_period=30_000.0, display_name="Inner",
        reference_body_name="Sun",
    )
    system: CelestialSystem = build_tree([sun, home, inner])
    return system, system.bodies["Inner"]


def _make_system_with_subsystem():
    """Build Sun + Home + Barycenter(child1, child2) for sub-system route tests."""
    from kopdeltav.system import CelestialSystem

    sun = CelestialBody(
        name="Sun", radius=261_600_000.0, gee_asl=28.0, has_ocean=False,
        atmosphere=None, orbit=None, rotational_period=432_000.0, display_name="Sun",
    )
    home = CelestialBody(
        name="Home", radius=600_000.0, gee_asl=1.0, has_ocean=False,
        atmosphere=None,
        orbit=OrbitalElements(
            semi_major_axis=13_599_840_256.0, eccentricity=0.0, inclination=0.0,
            argument_of_periapsis=0.0, longitude_of_ascending_node=0.0,
            mean_anomaly_at_epoch=0.0, epoch=0.0,
        ),
        rotational_period=21_600.0, display_name="Home", is_home_world=True,
        reference_body_name="Sun",
    )
    bary = CelestialBody(
        name="Bary", radius=10_000.0, gee_asl=1.0, has_ocean=False,
        atmosphere=None,
        orbit=OrbitalElements(
            semi_major_axis=150_000_000_000_000.0, eccentricity=0.0, inclination=0.0,
            argument_of_periapsis=0.0, longitude_of_ascending_node=0.0,
            mean_anomaly_at_epoch=0.0, epoch=0.0,
        ),
        rotational_period=50_000.0, display_name="Bary",
        reference_body_name="Sun",
    )
    child1 = CelestialBody(
        name="FarWorld", radius=500_000.0, gee_asl=0.8, has_ocean=False,
        atmosphere=None,
        orbit=OrbitalElements(
            semi_major_axis=11_464_286_293.0, eccentricity=0.0, inclination=0.0,
            argument_of_periapsis=0.0, longitude_of_ascending_node=0.0,
            mean_anomaly_at_epoch=0.0, epoch=0.0,
        ),
        rotational_period=40_000.0, display_name="FarWorld",
        reference_body_name="Bary",
    )
    child2 = CelestialBody(
        name="Star2", radius=100_000.0, gee_asl=5.0, has_ocean=False,
        atmosphere=None,
        orbit=OrbitalElements(
            semi_major_axis=119_128_788.0, eccentricity=0.0, inclination=0.0,
            argument_of_periapsis=0.0, longitude_of_ascending_node=0.0,
            mean_anomaly_at_epoch=0.0, epoch=0.0,
        ),
        rotational_period=10_000.0, display_name="Star2",
        reference_body_name="Bary",
    )
    system: CelestialSystem = build_tree([sun, home, bary, child1, child2])
    return system, system.bodies["Bary"], system.bodies["FarWorld"]


class TestComputeRouteInnerPlanet:
    def test_route_to_inner_planet(self) -> None:
        """Route to an inner planet (SMA < home SMA) must succeed."""
        system, inner = _make_system_with_inner_planet()
        steps = compute_route(system, destination=inner)
        assert len(steps) == 5
        assert all(s.dv > 0 for s in steps)

    def test_inner_planet_cumulative(self) -> None:
        system, inner = _make_system_with_inner_planet()
        steps = compute_route(system, destination=inner)
        running = 0.0
        for step in steps:
            running += step.dv
            assert math.isclose(step.cumulative, running, rel_tol=1e-9)


class TestComputeRouteSubSystem:
    def test_route_to_subsystem_body(self) -> None:
        """Route to a body inside a sub-star-system (destination=bary, moon=child)."""
        system, bary, farworld = _make_system_with_subsystem()
        steps = compute_route(system, destination=bary, moon=farworld)
        assert len(steps) == 6
        assert all(s.dv > 0 for s in steps)

    def test_subsystem_cumulative(self) -> None:
        system, bary, farworld = _make_system_with_subsystem()
        steps = compute_route(system, destination=bary, moon=farworld)
        running = 0.0
        for step in steps:
            running += step.dv
            assert math.isclose(step.cumulative, running, rel_tol=1e-9)
```

- [ ] **Step 3: Run new tests to verify they fail**

Run: `pytest tests/test_calculator.py::TestComputeRouteInnerPlanet tests/test_calculator.py::TestComputeRouteSubSystem -v`
Expected: FAIL (inner planet raises ValueError, SegmentType not found)

- [ ] **Step 4: Update compute_route with SegmentType tags and inner planet support**

The inner planet route already works after Task 1's `calculate_hohmann` fix. The main change is adding `segment_type` to each `_add` call. Replace `compute_route` function body:

```python
    home = system.home_world

    steps: list[DvStep] = []
    cumulative = 0.0

    def _add(label: str, dv: float, seg_type: SegmentType, note: str = "") -> None:
        nonlocal cumulative
        cumulative += dv
        steps.append(DvStep(
            label=label, dv=dv, cumulative=cumulative,
            segment_type=seg_type, note=note,
        ))

    # Step 1: Launch to low orbit.
    lo_alt = low_orbit_altitude(home)
    launch = calculate_launch(home, lo_alt)
    _add("Launch to low orbit", launch.total_rocket, SegmentType.LAUNCH)

    # --- Home-world moon route (no escape needed) ---
    if destination is not None and destination.parent is home:
        if destination.orbit is None:
            raise ValueError(f"Destination '{destination.name}' has no orbital elements.")
        dest_sma = destination.orbit.semi_major_axis
        hoh = calculate_hohmann(home, lo_alt, dest_sma)
        _add(f"Transfer to {destination.name}", hoh.departure_dv, SegmentType.TRANSFER)

        if moon is None:
            pdv, adv = landing_dv(destination)
            note = f"aerobrake option: {adv:.0f} m/s" if adv is not None else ""
            _add(f"Land on {destination.name}", pdv, SegmentType.LANDING, note=note)
        else:
            if moon.orbit is None:
                raise ValueError(f"Moon '{moon.name}' has no orbital elements.")
            esc_dest = escape_dv_from_low_orbit(destination)
            _add(f"Capture at {destination.name}", esc_dest, SegmentType.CAPTURE)
            dest_lo = low_orbit_altitude(destination)
            mhoh = calculate_hohmann(destination, dest_lo, moon.orbit.semi_major_axis)
            _add(f"Transfer to {moon.name}", mhoh.departure_dv, SegmentType.MOON_TRANSFER)
            pdv_m, adv_m = landing_dv(moon)
            note_m = f"aerobrake option: {adv_m:.0f} m/s" if adv_m is not None else ""
            _add(f"Land on {moon.name}", pdv_m, SegmentType.MOON_LANDING, note=note_m)
        return steps

    # --- Interplanetary route ---
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
```

- [ ] **Step 5: Make LaunchResult and TsiolkovskyResult frozen**

```python
@dataclass(frozen=True)
class LaunchResult:
    # ... (keep existing fields and docstring)

@dataclass(frozen=True)
class TsiolkovskyResult:
    # ... (keep existing fields and docstring)
```

- [ ] **Step 6: Add is_barycenter helper to system.py**

Add to `kopdeltav/system.py` after `sort_by_transfer_dv`:

```python
def is_barycenter(body: CelestialBody) -> bool:
    """Heuristic: detect if a body is likely a system barycenter.

    天体がバリセンタ(重心)かどうかをヒューリスティクスで判定する。

    A body is treated as a barycenter when it has children and its
    radius is smaller than the smallest child's radius. This correctly
    identifies bodies like Chaos (R=10km with children R>>10km)
    without false-positiving on normal planets with small moons.

    Args:
        body: The body to check.

    Returns:
        True if the body is likely a barycenter.
    """
    if not body.children:
        return False
    min_child_radius = min(c.radius for c in body.children)
    return body.radius < min_child_radius
```

- [ ] **Step 7: Update run.py interactive mode for barycenter forced selection**

In `run.py`, in the `_interactive_mode` loop where the user selects a destination (around line 345), after `dest_body, _, _is_home_moon = all_dest[idx]`, add:

```python
        # Import at top of file
        from kopdeltav.system import is_barycenter

        # Force sub-body selection for barycenters
        sub_moons = dest_body.children
        moon: CelestialBody | None = None

        if is_barycenter(dest_body) and not sub_moons:
            print(f"  {dest_body.display_name} はバリセンタです。子天体がありません。")
            continue

        if is_barycenter(dest_body):
            # Must pick a child — landing on barycenter is not meaningful
            print(f"\n{dest_body.display_name} 系の天体を選択してください:")
            for j, m in enumerate(sub_moons, 1):
                m_display = m.display_name if m.display_name != m.name else m.name
                m_label = f"{m.name} ({m_display})" if m_display != m.name else m.name
                m_info = _body_brief(m)
                print(f"  {j}) {m_label}")
                print(f"     {m_info}")
            # No "Enter for body" option — must pick a child

            try:
                moon_raw = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if moon_raw == "":
                print("  バリセンタには着陸できません。天体を選んでください。")
                continue

            try:
                moon_idx = int(moon_raw) - 1
                if 0 <= moon_idx < len(sub_moons):
                    moon = sub_moons[moon_idx]
                else:
                    print(f"  1〜{len(sub_moons)} の番号を入力してください。")
                    continue
            except ValueError:
                print("  無効な入力です。")
                continue
        elif sub_moons:
            # Original moon selection (non-barycenter with moons)
```

- [ ] **Step 8: Update existing test imports for SegmentType**

In `tests/test_calculator.py`, update imports:

```python
from kopdeltav.calculator import (
    DvStep,
    HohmannResult,
    SegmentType,
    calculate_hohmann,
    # ... rest of imports
)
```

- [ ] **Step 9: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 10: Run linters and type check**

Run: `ruff check kopdeltav/ run.py tests/ && ruff format kopdeltav/ run.py tests/ && mypy --strict kopdeltav/`
Expected: Clean

- [ ] **Step 11: Commit**

```bash
git add kopdeltav/calculator.py kopdeltav/system.py run.py tests/test_calculator.py
git commit -m "feat(calculator): add SegmentType enum, frozen dataclasses, barycenter detection

DvStep and LaunchResult are now frozen. SegmentType enum tags each route
step for display coloring. is_barycenter() heuristic forces sub-body
selection for system barycenters like Chaos. Inner planet routes now
work via calculate_hohmann inward support."
```

---

## Task 3: CLI Internationalization

**Branch:** `dev/feature/cli-i18n`
**Issue:** #2

**Files:**
- Modify: `kopdeltav/i18n.py`
- Modify: `run.py`
- Modify: `tests/test_i18n.py`

- [ ] **Step 1: Write failing tests for detect_language and Indonesian**

Add to `tests/test_i18n.py`:

```python
import os
from unittest.mock import patch

from kopdeltav.i18n import SUPPORTED_LANGUAGES, detect_language, get_text


class TestDetectLanguage:
    def test_override_takes_priority(self) -> None:
        assert detect_language(override="id") == "id"

    def test_lang_env(self) -> None:
        with patch.dict(os.environ, {"LANG": "ja_JP.UTF-8"}, clear=False):
            assert detect_language() == "ja"

    def test_lc_messages_priority(self) -> None:
        with patch.dict(os.environ, {"LC_MESSAGES": "id_ID.UTF-8", "LANG": "en_US.UTF-8"}, clear=False):
            assert detect_language() == "id"

    def test_unknown_falls_back_to_en(self) -> None:
        with patch.dict(os.environ, {"LANG": "xx_XX.UTF-8"}, clear=True):
            assert detect_language() == "en"

    def test_empty_env_defaults_to_en(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            # Remove all locale vars
            for key in ("LC_MESSAGES", "LANG", "LC_ALL"):
                os.environ.pop(key, None)
            assert detect_language() == "en"


class TestIndonesian:
    def test_id_in_supported(self) -> None:
        assert "id" in SUPPORTED_LANGUAGES

    def test_all_en_keys_exist_in_id(self) -> None:
        from kopdeltav.i18n import get_all_keys
        en_keys = set(get_all_keys("en").keys())
        id_keys = set(get_all_keys("id").keys())
        missing = en_keys - id_keys
        assert not missing, f"Missing Indonesian keys: {missing}"

    def test_all_en_keys_exist_in_ja(self) -> None:
        from kopdeltav.i18n import get_all_keys
        en_keys = set(get_all_keys("en").keys())
        ja_keys = set(get_all_keys("ja").keys())
        missing = en_keys - ja_keys
        assert not missing, f"Missing Japanese keys: {missing}"


class TestKeyFallback:
    def test_undefined_key_returns_en_fallback(self) -> None:
        result = get_text("common.calculate", "id")
        assert result != "common.calculate"  # Should return actual translation

    def test_completely_unknown_key_returns_key(self) -> None:
        result = get_text("nonexistent.key", "en")
        assert result == "nonexistent.key"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_i18n.py -v`
Expected: FAIL (detect_language not found, "id" not in SUPPORTED_LANGUAGES)

- [ ] **Step 3: Add detect_language() and Indonesian translations to i18n.py**

Add `detect_language` function and Indonesian translations to `kopdeltav/i18n.py`. Update `SUPPORTED_LANGUAGES` to `("ja", "en", "id")`. Add the full Indonesian `"id"` section to `_TRANSLATIONS` mirroring the `"en"` section with Indonesian text. Update `get_text()` to fall back to English when a key is missing in the requested language.

The `detect_language` function:

```python
import locale
import logging
import os

_i18n_logger = logging.getLogger(__name__)
_warned_keys: set[str] = set()


def detect_language(override: str | None = None) -> str:
    """Detect the user's preferred language.

    ユーザーの優先言語を検出する。

    Priority:
        1. override parameter (from --lang flag)
        2. LC_MESSAGES environment variable
        3. LANG environment variable
        4. LC_ALL environment variable
        5. locale.getlocale()
        6. Fallback: "en"

    Args:
        override: Explicit language code from CLI flag.

    Returns:
        Two-letter language code ("ja", "en", or "id").
    """
    if override and override in SUPPORTED_LANGUAGES:
        return override

    def _extract(raw: str) -> str | None:
        code = raw.split("_")[0].split(".")[0].lower()
        return code if code in SUPPORTED_LANGUAGES else None

    for env_var in ("LC_MESSAGES", "LANG", "LC_ALL"):
        val = os.environ.get(env_var, "")
        if val:
            result = _extract(val)
            if result:
                return result

    try:
        loc, _ = locale.getlocale()
        if loc:
            result = _extract(loc)
            if result:
                return result
    except ValueError:
        pass

    return "en"
```

Update `get_text()` to fall back to English:

```python
def get_text(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    parts = key.split(".", maxsplit=1)
    if len(parts) != 2:
        return key

    category, name = parts

    # Try requested language first.
    lang_dict = _TRANSLATIONS[lang]
    category_dict = lang_dict.get(category)
    if category_dict is not None:
        value = category_dict.get(name)
        if value is not None:
            return value

    # Fall back to English.
    if lang != "en":
        en_dict = _TRANSLATIONS["en"]
        en_category = en_dict.get(category)
        if en_category is not None:
            value = en_category.get(name)
            if value is not None:
                if key not in _warned_keys:
                    _warned_keys.add(key)
                    _i18n_logger.warning("Missing i18n key '%s' for lang '%s'; using English", key, lang)
                return value

    return key
```

Add the Indonesian translations (full `"id"` section — all keys matching `"en"` structure). Add these new keys to all three languages:

- `"body.radius_short"`: ja="半径", en="R", id="R" (for `_body_brief`)
- `"route.step"`: ja="ステップ", en="Step", id="Langkah" (for markdown table)
- `"route.dv"`: ja="ΔV", en="ΔV", id="ΔV" (for markdown table header)
- `"route.total"`: ja="合計", en="Total", id="Total" (for markdown/display)

- [ ] **Step 4: Run i18n tests**

Run: `pytest tests/test_i18n.py -v`
Expected: ALL PASS

- [ ] **Step 5: Add --lang flag to run.py**

Replace the manual `sys.argv` parsing in `run.py:main()` with `argparse`:

```python
import argparse

def main() -> None:
    parser = argparse.ArgumentParser(
        description="KSPDeltaVForMods — ΔV calculator for KSP1 planet pack mods"
    )
    parser.add_argument("config", nargs="?", help="Path to a Kopernicus .cfg file")
    parser.add_argument("--scan", metavar="GAMEDATA", help="Scan GameData directory")
    parser.add_argument("--interactive", action="store_true", help="Load saved data")
    parser.add_argument("--lang", choices=["ja", "en", "id"], help="UI language")
    args = parser.parse_args()

    lang = detect_language(override=args.lang)
    # Pass lang to all display functions...
```

- [ ] **Step 6: Replace all hardcoded strings in run.py with get_text()**

Thread `lang` parameter through `_body_brief`, `_print_body`, `_print_home_info`, `_print_route`, `_print_dest_list`, and `_interactive_mode`. Replace every hardcoded Japanese/English string with `get_text("key", lang)`.

Example for `_body_brief`:

```python
def _body_brief(body: CelestialBody, lang: str = "ja") -> str:
    r_km = body.radius / 1000
    radius_label = get_text("body.radius_short", lang)
    parts: list[str] = [f"{radius_label}:{_fmt_number(r_km)}km", f"g:{body.gee_asl:.2f}"]
    if body.atmosphere is not None:
        atmo_km = body.atmosphere.atmosphere_depth / 1000
        parts.append(f"{get_text('body.has_atmosphere', lang)}:{_fmt_number(atmo_km)}km")
    else:
        parts.append(get_text("body.no_atmosphere", lang))
    if body.children:
        parts.append(f"{get_text('system.moons', lang)}x{len(body.children)}")
    return "  ".join(parts)
```

- [ ] **Step 7: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 8: Run linters**

Run: `ruff check kopdeltav/ run.py tests/ && ruff format kopdeltav/ run.py tests/ && mypy --strict kopdeltav/`
Expected: Clean

- [ ] **Step 9: Commit**

```bash
git add kopdeltav/i18n.py run.py tests/test_i18n.py
git commit -m "feat(i18n): add Indonesian language, locale detection, CLI --lang flag

detect_language() checks LC_MESSAGES > LANG > LC_ALL > locale.getlocale()
with --lang override. Indonesian translations added. All run.py hardcoded
strings replaced with get_text(). Missing keys fall back to English with
logged warning."
```

---

## Task 4: Subway-Map Display, Detail View & Output Formats

**Branch:** `dev/feature/subway-map-display`
**Issue:** #3

**Files:**
- Modify: `run.py`
- Create: `tests/test_display.py`

- [ ] **Step 1: Add terminal capability detection to run.py**

Add at the top of `run.py`:

```python
import os
import signal
import sys

def _supports_color() -> bool:
    """Detect if terminal supports ANSI color."""
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    return True

def _supports_unicode() -> bool:
    """Detect if stdout encoding supports Unicode."""
    enc = getattr(sys.stdout, "encoding", "") or ""
    return "utf" in enc.lower()

def _enable_ansi_on_windows() -> None:
    """Enable ANSI escape codes on Windows 10+."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass

# SIGPIPE handling
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, OSError):
    pass  # Windows has no SIGPIPE
```

- [ ] **Step 2: Create the subway-map renderer**

Add to `run.py`:

```python
# ANSI color codes
_COLORS: dict[str, str] = {
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "cyan": "\033[36m",
    "red": "\033[31m",
    "reset": "\033[0m",
    "bold": "\033[1m",
}

_SEGMENT_COLORS: dict[str, str] = {
    "launch": "green",
    "escape": "yellow",
    "transfer": "blue",
    "capture": "cyan",
    "landing": "red",
    "system_escape": "yellow",
    "moon_transfer": "blue",
    "moon_landing": "red",
}

def _color(text: str, color_name: str, use_color: bool) -> str:
    if not use_color:
        return text
    code = _COLORS.get(color_name, "")
    reset = _COLORS["reset"]
    return f"{code}{text}{reset}"

def _node(solid: bool, use_unicode: bool) -> str:
    if use_unicode:
        return "●" if solid else "○"
    return "(*)" if solid else "(o)"

def _arrow(accel: bool, use_unicode: bool) -> str:
    if use_unicode:
        return "▲" if accel else "▼"
    return "^" if accel else "v"

def _pipe(use_unicode: bool) -> str:
    return "│" if use_unicode else "|"

def _print_subway_route(
    steps: list[DvStep],
    home_name: str,
    dest_name: str,
    lang: str,
    use_color: bool,
    use_unicode: bool,
) -> None:
    """Print route in subway-map style."""
    pipe = _pipe(use_unicode)
    header = f"── ΔV Route: {home_name} → {dest_name} "
    print(_color(header + "─" * max(0, 50 - len(header)), "bold", use_color))
    print()

    # Start node
    print(f"  {_node(True, use_unicode)} {home_name} (surface)")

    for step in steps:
        seg_color = _SEGMENT_COLORS.get(step.segment_type.value, "blue")
        is_accel = step.segment_type.value in ("launch", "escape", "transfer", "system_escape")
        arrow = _arrow(is_accel, use_unicode)

        dv_str = f"{_fmt_number(step.dv, 0):>8} m/s"
        line = f"  {pipe}  {arrow} {_color(dv_str, seg_color, use_color)}   {step.label}"
        print(line)

        # Intermediate node
        is_solid = step.segment_type.value in ("launch", "landing", "capture")
        is_landing = step.segment_type.value == "landing"

        if not is_landing:
            node_label = _node_label_for_step(step)
            print(f"  {_node(is_solid, use_unicode)}─ {node_label}")

    # End node
    print(f"  {_node(True, use_unicode)} {dest_name} (surface)")
    print()
    total = steps[-1].cumulative if steps else 0.0
    print(f"  Total: {_color(_fmt_number(total, 0) + ' m/s', 'bold', use_color)}")


def _node_label_for_step(step: DvStep) -> str:
    """Derive an intermediate node label from a route step."""
    label = step.label
    if "Launch" in label or "low orbit" in label.lower():
        return "Low orbit"
    if "Escape" in label:
        body_name = label.replace("Escape ", "")
        return f"{body_name} SOI edge"
    if "Transfer" in label:
        return "Transfer orbit"
    if "Capture" in label:
        body_name = label.replace("Capture at ", "")
        return f"{body_name} low orbit"
    return label
```

- [ ] **Step 3: Add detail view renderer**

```python
def _print_detail_block(
    step: DvStep,
    body: CelestialBody | None,
    launch_result: LaunchResult | None,
    hohmann_result: HohmannResult | None,
    use_unicode: bool,
    lang: str,
) -> None:
    """Print detail sub-items under a route step."""
    pipe = _pipe(use_unicode)
    branch = "├" if use_unicode else "+--"
    end = "└" if use_unicode else "\\--"

    details: list[str] = []

    if launch_result is not None and step.segment_type == SegmentType.LAUNCH:
        details.append(f"{get_text('launch.orbital_velocity', lang)}: {_fmt_number(launch_result.orbital_velocity, 1)} m/s")
        details.append(f"{get_text('launch.gravity_loss', lang)}: {_fmt_number(launch_result.gravity_loss, 1)} m/s")
        details.append(f"{get_text('launch.drag_loss', lang)}: {_fmt_number(launch_result.drag_loss, 1)} m/s")
        if launch_result.jet_savings > 0:
            details.append(f"{get_text('launch.jet_savings', lang)}: -{_fmt_number(launch_result.jet_savings, 1)} m/s")

    if hohmann_result is not None and step.segment_type == SegmentType.TRANSFER:
        t = hohmann_result.transfer_time
        days = int(t // 86400)
        hours = int((t % 86400) // 3600)
        time_str = f"{days}d {hours}h" if days > 0 else f"{hours}h {int((t % 3600) // 60)}m"
        details.append(f"{get_text('hohmann.transfer_time', lang)}: {time_str}")

    if body is not None and step.segment_type == SegmentType.CAPTURE:
        details.append(f"{get_text('body.radius', lang)}: {_fmt_number(body.radius / 1000)} km")
        details.append(f"{get_text('body.gravity', lang)}: {body.gee_asl:.2f}g")
        if body.atmosphere:
            details.append(f"{get_text('body.atmosphere', lang)}: {_fmt_number(body.atmosphere.atmosphere_depth / 1000)} km")
        if body.soi > 0:
            details.append(f"SOI: {_fmt_number(body.soi / 1000)} km")

    if step.note and "aerobrake" in step.note:
        details.append(step.note)

    for i, detail in enumerate(details):
        connector = end if i == len(details) - 1 else branch
        print(f"  {pipe}    {connector} {detail}")
```

- [ ] **Step 4: Add --format and --detail flags to argparse**

In `run.py` `main()`:

```python
    parser.add_argument("--detail", action="store_true", help="Show detailed route info")
    parser.add_argument("--format", choices=["text", "md", "json"], default="text",
                        help="Output format (default: text)")
```

- [ ] **Step 5: Add JSON and Markdown output formatters**

```python
import json as json_mod

def _route_to_json(steps: list[DvStep], home_name: str, dest_name: str) -> str:
    """Serialize route to JSON."""
    segments = []
    for step in steps:
        segments.append({
            "type": step.segment_type.value,
            "label": step.label,
            "dv": round(step.dv, 1),
            "cumulative": round(step.cumulative, 1),
            "note": step.note or None,
        })
    data = {
        "route": {
            "from": home_name,
            "to": dest_name,
            "total_dv": round(steps[-1].cumulative, 1) if steps else 0.0,
            "segments": segments,
        }
    }
    return json_mod.dumps(data, indent=2, ensure_ascii=False)


def _route_to_markdown(steps: list[DvStep], home_name: str, dest_name: str, lang: str) -> str:
    """Serialize route to Markdown table."""
    lines = [
        f"## ΔV Route: {home_name} → {dest_name}",
        "",
        f"| # | {get_text('route.launch', lang)} | ΔV (m/s) | {get_text('route.cumulative', lang)} (m/s) |",
        "|---|------|---------|------------|",
    ]
    for i, step in enumerate(steps, 1):
        lines.append(f"| {i} | {step.label} | {_fmt_number(step.dv, 0)} | {_fmt_number(step.cumulative, 0)} |")
    if steps:
        lines.append(f"\n**Total: {_fmt_number(steps[-1].cumulative, 0)} m/s**")
    return "\n".join(lines)
```

- [ ] **Step 6: Write display tests**

Create `tests/test_display.py`:

```python
"""Tests for CLI display functions."""
from __future__ import annotations

import json
import os
from unittest.mock import patch

from kopdeltav.calculator import DvStep, SegmentType


class TestRouteToJson:
    def test_valid_json(self) -> None:
        from run import _route_to_json
        steps = [
            DvStep(label="Launch", dv=3108.0, cumulative=3108.0, segment_type=SegmentType.LAUNCH),
            DvStep(label="Escape", dv=1053.0, cumulative=4161.0, segment_type=SegmentType.ESCAPE),
        ]
        result = _route_to_json(steps, "Kerbin", "Target")
        data = json.loads(result)
        assert data["route"]["from"] == "Kerbin"
        assert data["route"]["to"] == "Target"
        assert len(data["route"]["segments"]) == 2
        assert data["route"]["total_dv"] == 4161.0

    def test_empty_route(self) -> None:
        from run import _route_to_json
        result = _route_to_json([], "A", "B")
        data = json.loads(result)
        assert data["route"]["total_dv"] == 0.0


class TestRouteToMarkdown:
    def test_valid_markdown(self) -> None:
        from run import _route_to_markdown
        steps = [
            DvStep(label="Launch", dv=3108.0, cumulative=3108.0, segment_type=SegmentType.LAUNCH),
            DvStep(label="Escape", dv=1053.0, cumulative=4161.0, segment_type=SegmentType.ESCAPE),
        ]
        result = _route_to_markdown(steps, "Kerbin", "Target", "en")
        assert "| 1 |" in result
        assert "| 2 |" in result
        assert "4,161" in result


class TestSubwayMapSnapshot:
    def test_no_ansi_in_no_color_mode(self) -> None:
        """Subway-map output must contain no ANSI escape codes when color is off."""
        from io import StringIO
        from run import _print_subway_route
        import sys
        buf = StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        steps = [
            DvStep(label="Launch to low orbit", dv=3108.0, cumulative=3108.0, segment_type=SegmentType.LAUNCH),
        ]
        _print_subway_route(steps, "Kerbin", "Target", "en", use_color=False, use_unicode=True)
        sys.stdout = old_stdout
        output = buf.getvalue()
        assert "\033[" not in output
        assert "3,108" in output

    def test_ascii_fallback(self) -> None:
        """When use_unicode=False, output must not contain Unicode box-drawing chars."""
        from io import StringIO
        from run import _print_subway_route
        import sys
        buf = StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        steps = [
            DvStep(label="Launch to low orbit", dv=3108.0, cumulative=3108.0, segment_type=SegmentType.LAUNCH),
        ]
        _print_subway_route(steps, "Kerbin", "Target", "en", use_color=False, use_unicode=False)
        sys.stdout = old_stdout
        output = buf.getvalue()
        assert "●" not in output
        assert "│" not in output
        assert "(*)" in output or "|" in output


class TestTerminalDetection:
    def test_no_color_env(self) -> None:
        from run import _supports_color
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            assert _supports_color() is False

    def test_dumb_terminal(self) -> None:
        from run import _supports_color
        with patch.dict(os.environ, {"TERM": "dumb"}):
            assert _supports_color() is False
```

- [ ] **Step 7: Integrate into _interactive_mode**

Replace `_print_route` calls with the new subway-map renderer in `_interactive_mode`. Use `--format` and `--detail` flags from argparse. Wire up the `_print_subway_route` and optionally `_print_detail_block` calls.

- [ ] **Step 8: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 9: Run linters**

Run: `ruff check kopdeltav/ run.py tests/ && ruff format kopdeltav/ run.py tests/ && mypy --strict kopdeltav/`
Expected: Clean

- [ ] **Step 10: Commit**

```bash
git add run.py tests/test_display.py
git commit -m "feat(cli): subway-map route display, detail view, output formats

Add ANSI-colored subway-map route renderer with Unicode/ASCII fallback.
Terminal capability auto-detection (color, unicode, Windows ANSI).
--detail flag for expanded route info. --format text/md/json output.
SIGPIPE handling for pipe safety."
```

---

## Task 5: README, LICENSE, CHANGELOG (Parallel — worktree)

**Branch:** `dev/docs/readme-license-changelog`
**Issue:** #4

**Files:**
- Create: `README.md`, `README-ja.md`, `README-id.md`, `LICENSE`, `CHANGELOG.md`

This task runs in a separate git worktree, parallel with Tasks 1-4.

- [ ] **Step 1: Create LICENSE**

MIT license with `Yumeno Yuuka` and year 2026.

- [ ] **Step 2: Create CHANGELOG.md**

Keep a Changelog format with `[0.1.0] - 2026-03-26` section.

- [ ] **Step 3: Create README.md (English main)**

Follow the user's README template. Include:
- Project name + badges (CI, License, Python)
- Overview: KSP1 + Kopernicus ΔV calculator
- Features list
- Tech stack table
- Getting started (python run.py --scan / --interactive)
- Output sample (subway-map text example)
- i18n section (detection priority, --lang)
- Windows color notes
- JSON schema brief
- **KSP2 not supported** note
- Language links at top: `[日本語](README-ja.md) | [Bahasa Indonesia](README-id.md)`
- License: MIT

- [ ] **Step 4: Create README-ja.md**

Japanese translation of README.md.

- [ ] **Step 5: Create README-id.md**

Indonesian translation of README.md.

- [ ] **Step 6: Commit**

```bash
git add README.md README-ja.md README-id.md LICENSE CHANGELOG.md
git commit -m "docs: add README (en/ja/id), LICENSE (MIT), CHANGELOG"
```

---

## Task 6: CI Workflow + Release (Parallel — worktree)

**Branch:** `dev/chore/ci-release`
**Issue:** #5

**Files:**
- Create: `.github/workflows/ci.yml`

This task runs in a separate git worktree, parallel with Tasks 1-4.

- [ ] **Step 1: Create CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main, dev, "dev/**"]
  pull_request:
    branches: [main, dev]

jobs:
  python:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Cache pip
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('pyproject.toml') }}
          restore-keys: ${{ runner.os }}-pip-
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Lint
        run: ruff check kopdeltav/ api.py run.py tests/
      - name: Format check
        run: ruff format --check kopdeltav/ api.py run.py tests/
      - name: Type check
        run: mypy --strict kopdeltav/
      - name: Tests
        run: pytest tests/ -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow (lint, type-check, test)"
```

- [ ] **Step 3: Tag v0.1.0 on dev**

After merging all branches to dev:

```bash
git tag -a v0.1.0 -m "v0.1.0: Core library + CLI"
```

(Release creation is manual via GitHub UI after push.)

---

## Task 7: Integration & Merge

**Branch:** `dev`

- [ ] **Step 1: Merge #4 (docs) to dev**

```bash
git merge dev/docs/readme-license-changelog --no-ff
```

- [ ] **Step 2: Merge #5 (CI) to dev**

```bash
git merge dev/chore/ci-release --no-ff
```

- [ ] **Step 3: Merge #1 (inner planet + sub-system) to dev**

```bash
git merge dev/fix/inner-planet-hohmann --no-ff
```

- [ ] **Step 4: Merge #2 (i18n) to dev**

```bash
git merge dev/feature/cli-i18n --no-ff
```

- [ ] **Step 5: Merge #3 (subway-map) to dev**

```bash
git merge dev/feature/subway-map-display --no-ff
```

- [ ] **Step 6: Run full validation**

```bash
ruff check kopdeltav/ api.py run.py tests/
ruff format --check kopdeltav/ api.py run.py tests/
mypy --strict kopdeltav/
pytest tests/ -v
```

- [ ] **Step 7: Tag v0.2.0**

```bash
git tag -a v0.2.0 -m "v0.2.0: i18n, subway-map display, inner planet routing"
```

- [ ] **Step 8: Update CHANGELOG.md with v0.2.0 date**

Replace `2026-03-xx` with actual date.

- [ ] **Step 9: Push dev + tags**

```bash
git push origin dev --tags
```
