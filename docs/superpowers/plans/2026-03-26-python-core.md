# Python Core Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `kopdeltav/` Python core library — data models, Kopernicus config parser, stock Kerbal system data, GameData discovery, Delta-V calculator, i18n, and CLI.

**Architecture:** Layered library with zero external dependencies. `models.py` defines data structures, `stock.py` provides built-in Kerbal system data, `parser.py` reads Kopernicus `.cfg` files and applies patches to stock data, `discovery.py` finds GameData folders, `calculator.py` computes orbital mechanics, `i18n.py` handles translations, and `run.py` provides a CLI entry point.

**Tech Stack:** Python 3.10+ (stdlib only for `kopdeltav/`), pytest for testing, ruff for formatting/linting, mypy for type checking.

**Spec:** `docs/superpowers/specs/2026-03-26-python-core-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Create | Project config (ruff, mypy, pytest, dependencies) |
| `kopdeltav/__init__.py` | Create | Package init, public API exports |
| `kopdeltav/models.py` | Create | CurveKey, Atmosphere, OrbitalElements, CelestialBody, hermite_interp, compute_mu |
| `kopdeltav/stock.py` | Create | Stock Kerbal system (17 bodies with atmosphere curves) |
| `kopdeltav/parser.py` | Create | ConfigNode parser, body extraction, patch application |
| `kopdeltav/discovery.py` | Create | find_gamedata, scan_kopernicus_configs |
| `kopdeltav/calculator.py` | Create | Orbital velocity, escape velocity, atmospheric density, launch ΔV, Hohmann, Tsiolkovsky |
| `kopdeltav/i18n.py` | Create | ja/en translation strings |
| `run.py` | Create | CLI entry point |
| `tests/__init__.py` | Create | Test package |
| `tests/test_models.py` | Create | Tests for models.py |
| `tests/test_stock.py` | Create | Tests for stock.py |
| `tests/test_parser.py` | Create | Tests for parser.py |
| `tests/test_discovery.py` | Create | Tests for discovery.py |
| `tests/test_calculator.py` | Create | Tests for calculator.py |
| `tests/test_i18n.py` | Create | Tests for i18n.py |
| `sample_configs/Sanctar.cfg` | Create | User provides this file — needed for parser tests |
| `CLAUDE.md` | Modify | Add stock.py, discovery.py, new test files to repo structure |

---

### Task 0: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `kopdeltav/__init__.py`
- Create: `tests/__init__.py`
- Create: `sample_configs/Sanctar.cfg` (user provides)

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"

[project]
name = "kopdeltav"
version = "0.1.0"
description = "Delta-V calculator for KSP1 planet pack mods"
requires-python = ">=3.10"
license = "MIT"

[project.optional-dependencies]
api = ["fastapi>=0.100", "uvicorn[standard]>=0.20"]
dev = ["pytest>=7.0", "ruff>=0.4", "mypy>=1.0"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create package init files**

`kopdeltav/__init__.py`:
```python
"""KSPDeltaVForMods — Delta-V calculator for KSP1 planet pack mods."""
from __future__ import annotations
```

`tests/__init__.py`: empty file

- [ ] **Step 3: Ask user for Sanctar.cfg**

User said they have this file. Ask them to place it at `sample_configs/Sanctar.cfg`.
If not available yet, create `sample_configs/` directory and continue — parser tests will be written against it later.

```bash
mkdir -p sample_configs
```

- [ ] **Step 4: Create virtual environment and install dev dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

- [ ] **Step 5: Verify tooling works**

```bash
ruff check kopdeltav/
mypy --strict kopdeltav/
pytest tests/ -v
```

Expected: all pass (no files to lint/check yet, no tests to run)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml kopdeltav/__init__.py tests/__init__.py
git commit -m "chore: project scaffolding with pyproject.toml and package init"
```

---

### Task 1: models.py — Data Classes

**Files:**
- Create: `kopdeltav/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for CurveKey and compute_mu**

`tests/test_models.py`:
```python
from __future__ import annotations

import math

from kopdeltav.models import CurveKey, compute_mu, G0


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'kopdeltav.models'`

- [ ] **Step 3: Implement CurveKey, Atmosphere, OrbitalElements, compute_mu**

`kopdeltav/models.py`:
```python
"""Data models for celestial bodies, atmospheres, and orbital elements.

天体・大気・軌道を表現するデータ構造と補間関数。
"""
from __future__ import annotations

import math
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
        return (
            f"CelestialBody(name={self.name!r}, radius={self.radius}, "
            f"gee_asl={self.gee_asl})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CelestialBody):
            return NotImplemented
        return self.name == other.name and self.radius == other.radius

    def __hash__(self) -> int:
        return hash((self.name, self.radius))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Run ruff and mypy**

```bash
ruff check kopdeltav/models.py && ruff format kopdeltav/models.py && mypy --strict kopdeltav/models.py
```

- [ ] **Step 6: Commit**

```bash
git add kopdeltav/models.py tests/test_models.py
git commit -m "feat(models): add data classes — CurveKey, Atmosphere, OrbitalElements, CelestialBody"
```

---

### Task 2: models.py — hermite_interp

**Files:**
- Modify: `kopdeltav/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for hermite_interp**

Append to `tests/test_models.py`:
```python
import pytest

from kopdeltav.models import hermite_interp


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

    def test_linear_segment_zero_tangents(self) -> None:
        """With zero tangents, hermite degenerates but still interpolates."""
        keys = [
            CurveKey(0.0, 0.0, 0.0, 0.0),
            CurveKey(10.0, 10.0, 0.0, 0.0),
        ]
        # At midpoint with zero tangents: h00*0 + h10*0 + h01*10 + h11*0
        # h00(0.5)=0.5, h01(0.5)=0.5 => result = 5.0
        result = hermite_interp(keys, 5.0)
        assert math.isclose(result, 5.0, abs_tol=0.01)

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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models.py::TestHermiteInterp -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement hermite_interp**

Add to `kopdeltav/models.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: all PASS

- [ ] **Step 5: ruff + mypy**

```bash
ruff check kopdeltav/models.py && ruff format kopdeltav/models.py && mypy --strict kopdeltav/models.py
```

- [ ] **Step 6: Commit**

```bash
git add kopdeltav/models.py tests/test_models.py
git commit -m "feat(models): add hermite_interp — cubic Hermite spline interpolation"
```

---

### Task 3: stock.py — Stock Kerbal System Data

**Files:**
- Create: `kopdeltav/stock.py`
- Create: `tests/test_stock.py`

- [ ] **Step 1: Write failing tests**

`tests/test_stock.py`:
```python
from __future__ import annotations

import math

from kopdeltav.models import G0
from kopdeltav.stock import get_stock_body, get_stock_system


class TestStockSystem:
    def test_root_is_kerbol(self) -> None:
        root = get_stock_system()
        assert root.name == "Sun"

    def test_total_body_count(self) -> None:
        """Stock system has 17 bodies total."""
        def count(body: object) -> int:
            # CelestialBody has .children
            total = 1
            for child in getattr(body, "children", []):
                total += count(child)
            return total
        root = get_stock_system()
        assert count(root) == 17

    def test_kerbin_properties(self) -> None:
        kerbin = get_stock_body("Kerbin")
        assert kerbin is not None
        assert kerbin.radius == 600_000.0
        assert kerbin.gee_asl == 1.0
        expected_mu = 1.0 * G0 * 600_000.0**2
        assert math.isclose(kerbin.mu, expected_mu, rel_tol=1e-9)

    def test_kerbin_has_atmosphere(self) -> None:
        kerbin = get_stock_body("Kerbin")
        assert kerbin is not None
        assert kerbin.atmosphere is not None
        assert kerbin.atmosphere.atmosphere_depth == 70_000.0

    def test_mun_no_atmosphere(self) -> None:
        mun = get_stock_body("Mun")
        assert mun is not None
        assert mun.atmosphere is None

    def test_case_insensitive_lookup(self) -> None:
        assert get_stock_body("kerbin") is not None
        assert get_stock_body("KERBIN") is not None

    def test_unknown_body_returns_none(self) -> None:
        assert get_stock_body("NotABody") is None

    def test_parent_child_relationships(self) -> None:
        kerbin = get_stock_body("Kerbin")
        assert kerbin is not None
        assert kerbin.parent is not None
        assert kerbin.parent.name == "Sun"
        child_names = {c.name for c in kerbin.children}
        assert "Mun" in child_names
        assert "Minmus" in child_names

    def test_atmospheric_bodies(self) -> None:
        """Eve, Kerbin, Duna, Jool, Laythe should have atmospheres."""
        for name in ["Eve", "Kerbin", "Duna", "Jool", "Laythe"]:
            body = get_stock_body(name)
            assert body is not None, f"{name} not found"
            assert body.atmosphere is not None, f"{name} should have atmosphere"

    def test_non_atmospheric_bodies(self) -> None:
        for name in ["Moho", "Gilly", "Mun", "Minmus", "Ike", "Dres", "Vall", "Tylo", "Bop", "Pol", "Eeloo"]:
            body = get_stock_body(name)
            assert body is not None, f"{name} not found"
            assert body.atmosphere is None, f"{name} should not have atmosphere"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_stock.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement stock.py**

`kopdeltav/stock.py` — This is a large data file. Key structure:

```python
"""Stock Kerbal system body data (KSP 1.12.x).

KSP1 Stock 天体データ。ゲームソースから取得した値を内蔵。

All values sourced from KSP 1.12.x game data.
Atmospheric curves sourced from Squad/Bodies/<name>.cfg in stock GameData.
"""
from __future__ import annotations

import math
from functools import lru_cache

from kopdeltav.models import (
    Atmosphere,
    CelestialBody,
    CurveKey,
    OrbitalElements,
)


def _build_stock_tree() -> CelestialBody:
    """Build the complete stock Kerbal system tree.

    Stock 天体ツリーを構築する。

    Returns:
        Root body (Sun/Kerbol) with all children linked.
    """
    # --- Sun (Kerbol) ---
    sun = CelestialBody(
        name="Sun",
        radius=261_600_000.0,
        gee_asl=1.7462,
        has_ocean=False,
        atmosphere=None,
        orbit=None,
        rotational_period=432_000.0,
        display_name="Kerbol",
        soi=math.inf,
    )

    # --- Moho ---
    moho = CelestialBody(
        name="Moho",
        radius=250_000.0,
        gee_asl=0.275,
        has_ocean=False,
        atmosphere=None,
        orbit=OrbitalElements(
            semi_major_axis=5_263_138_304.0,
            eccentricity=0.2,
            inclination=7.0,
            argument_of_periapsis=15.0,
            longitude_of_ascending_node=70.0,
            mean_anomaly_at_epoch=3.14,
            epoch=0.0,
        ),
        rotational_period=1_210_000.0,
        display_name="Moho",
    )

    # ... (all 17 bodies defined similarly) ...
    # Bodies with atmospheres (Eve, Kerbin, Duna, Jool, Laythe) include
    # pressure_curve and temperature_curve with CurveKey data from game files.

    # --- Link parent-child and compute SOI ---
    _link_parent_child(sun, [moho, eve, kerbin, duna, dres, jool, eeloo])
    _link_parent_child(eve, [gilly])
    _link_parent_child(kerbin, [mun, minmus])
    _link_parent_child(duna, [ike])
    _link_parent_child(jool, [laythe, vall, tylo, bop, pol])

    return sun


def _link_parent_child(parent: CelestialBody, children: list[CelestialBody]) -> None:
    """Link parent-child relationships and compute SOI where needed.

    親子関係をリンクし、SOI が 0 の天体は a*(m/M)^(2/5) で計算する。
    """
    for child in children:
        child.parent = parent
        parent.children.append(child)
        if child.soi == 0.0 and child.orbit is not None:
            a = child.orbit.semi_major_axis
            child.soi = a * (child.mu / parent.mu) ** 0.4


@lru_cache(maxsize=1)
def get_stock_system() -> CelestialBody:
    """Return the stock Kerbal system root (Sun/Kerbol).

    Stock Kerbal 星系のルート天体を返す。lru_cache で 1 回だけ構築。

    Returns:
        Sun/Kerbol with all children recursively linked.
    """
    return _build_stock_tree()


def get_stock_body(name: str) -> CelestialBody | None:
    """Find a stock body by name (case-insensitive).

    名前で Stock 天体を検索する（大文字小文字区別なし）。

    Args:
        name: Body name to search for.

    Returns:
        CelestialBody if found, None otherwise.
    """
    target = name.lower()

    def _search(body: CelestialBody) -> CelestialBody | None:
        if body.name.lower() == target:
            return body
        for child in body.children:
            found = _search(child)
            if found is not None:
                return found
        return None

    return _search(get_stock_system())
```

**Important**: The full implementation must include all 17 bodies with accurate values from KSP 1.12.x:
- Sun, Moho, Eve, Gilly, Kerbin, Mun, Minmus, Duna, Ike, Dres, Jool, Laythe, Vall, Tylo, Bop, Pol, Eeloo
- Atmosphere curves for Eve, Kerbin, Duna, Jool, Laythe (pressure + temperature CurveKeys)
- All orbital elements
- All physical parameters (radius, geeASL, rotationalPeriod, hasOcean)

Source data from KSP Wiki or game files. Be precise with values.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_stock.py -v
```

Expected: all PASS

- [ ] **Step 5: ruff + mypy**

```bash
ruff check kopdeltav/stock.py && ruff format kopdeltav/stock.py && mypy --strict kopdeltav/stock.py
```

- [ ] **Step 6: Commit**

```bash
git add kopdeltav/stock.py tests/test_stock.py
git commit -m "feat(stock): add built-in stock Kerbal system data (17 bodies)"
```

---

### Task 4: parser.py — ConfigNode Tokenizer and Parser

**Files:**
- Create: `kopdeltav/parser.py`
- Create: `tests/test_parser.py`

This task implements the low-level ConfigNode parsing. Body extraction comes in Task 5.

- [ ] **Step 1: Write failing tests for ConfigNode parsing**

`tests/test_parser.py`:
```python
from __future__ import annotations

from kopdeltav.parser import ConfigNode, parse_config_node


class TestConfigNodeParser:
    def test_simple_key_value(self) -> None:
        text = "name = Kerbin"
        node = parse_config_node(text)
        assert node.get_value("name") == "Kerbin"

    def test_nested_block(self) -> None:
        text = """
        Body
        {
            name = Kerbin
            Properties
            {
                radius = 600000
            }
        }
        """
        node = parse_config_node(text)
        bodies = node.get_nodes("Body")
        assert len(bodies) == 1
        props = bodies[0].get_nodes("Properties")
        assert len(props) == 1
        assert props[0].get_value("radius") == "600000"

    def test_comment_removal(self) -> None:
        text = """
        name = Kerbin // this is a comment
        // full line comment
        radius = 600000
        """
        node = parse_config_node(text)
        assert node.get_value("name") == "Kerbin"
        assert node.get_value("radius") == "600000"

    def test_modifier_stripping_on_node_names(self) -> None:
        """Modifiers (@, !, %, +, -) should be stripped from node names."""
        text = """
        @Kopernicus
        {
            @Body[Kerbin]
            {
                %Properties
                {
                    radius = 700000
                }
            }
        }
        """
        node = parse_config_node(text)
        # Node names should have modifiers stripped
        kop = node.get_nodes("Kopernicus")
        assert len(kop) == 1
        # But original modifier is preserved in .modifier attribute
        assert kop[0].modifier == "@"

    def test_bracket_name_preserved(self) -> None:
        """Body[Kerbin] bracket syntax preserved in node name."""
        text = """
        @Body[Kerbin]
        {
            name = Kerbin
        }
        """
        node = parse_config_node(text)
        bodies = node.get_nodes("Body[Kerbin]")
        assert len(bodies) == 1
        assert bodies[0].modifier == "@"

    def test_pass_tag_stripped(self) -> None:
        """@Kopernicus:FINAL -> name='Kopernicus', modifier='@'."""
        text = """
        @Kopernicus:FINAL
        {
            Body
            {
                name = Test
            }
        }
        """
        node = parse_config_node(text)
        kop = node.get_nodes("Kopernicus")
        assert len(kop) == 1
        assert kop[0].modifier == "@"

    def test_needs_tag_stripped(self) -> None:
        """@Body[Kerbin]:NEEDS[Kopernicus] -> name='Body[Kerbin]'."""
        text = """
        @Body[Kerbin]:NEEDS[Kopernicus]
        {
            radius = 700000
        }
        """
        node = parse_config_node(text)
        bodies = node.get_nodes("Body[Kerbin]")
        assert len(bodies) == 1

    def test_delete_directive_detected(self) -> None:
        """!Body[Kerbin] {} should be parsed as a node with modifier '!'."""
        text = """
        !Body[Kerbin] {}
        """
        node = parse_config_node(text)
        deletes = node.get_nodes("Body[Kerbin]")
        assert len(deletes) == 1
        assert deletes[0].modifier == "!"

    def test_empty_input(self) -> None:
        node = parse_config_node("")
        assert node.get_value("anything") is None
        assert node.get_nodes("anything") == []

    def test_malformed_line_skipped(self) -> None:
        text = """
        name = Kerbin
        this is not valid
        radius = 600000
        """
        node = parse_config_node(text)
        assert node.get_value("name") == "Kerbin"
        assert node.get_value("radius") == "600000"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_parser.py::TestConfigNodeParser -v
```

Expected: FAIL

- [ ] **Step 3: Implement ConfigNode and parse_config_node**

Add to `kopdeltav/parser.py`:
```python
"""Kopernicus ConfigNode parser.

KSP Kopernicus の .cfg ファイルをパースし、CelestialBody を生成する。
"""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from kopdeltav.models import (
    Atmosphere,
    CelestialBody,
    CurveKey,
    OrbitalElements,
    compute_mu,
)


@dataclass
class ConfigNode:
    """Intermediate representation of a KSP ConfigNode.

    KSP ConfigNode の中間表現。key=value ペアとネストされた子ノードを保持する。

    Attributes:
        name: Node name with modifier stripped (e.g. "Body[Kerbin]", "Properties").
        modifier: Leading modifier character ("@", "!", "%", "+", "-") or "".
        values: Key-value pairs. Keys may repeat, so stored as list of tuples.
        children: Child ConfigNode list.
    """
    name: str = ""
    modifier: str = ""
    values: list[tuple[str, str]] = field(default_factory=list)
    children: list[ConfigNode] = field(default_factory=list)

    def get_value(self, key: str) -> str | None:
        """Get first value for a key, or None.

        指定キーの最初の値を返す。なければ None。
        """
        for k, v in self.values:
            if k == key:
                return v
        return None

    def get_all_values(self, key: str) -> list[str]:
        """Get all values for a key.

        指定キーの全値をリストで返す。
        """
        return [v for k, v in self.values if k == key]

    def get_nodes(self, name: str) -> list[ConfigNode]:
        """Get all child nodes with given name.

        指定名の子ノードを全て返す。
        """
        return [c for c in self.children if c.name == name]


_COMMENT_RE = re.compile(r"//.*$", re.MULTILINE)
_MODIFIER_RE = re.compile(r"^[@!+\-%]")


def _strip_modifier(name: str) -> tuple[str, str]:
    """Strip leading modifier and trailing pass tags from a node name.

    修飾子（@, !, +, -, %）とパスタグ（:FINAL, :BEFORE[x], :AFTER[x], :NEEDS[x]）
    を除去して (修飾子, クリーン名) を返す。

    Examples:
        "@Kopernicus:FINAL" -> ("@", "Kopernicus")
        "!Body[Kerbin]"     -> ("!", "Body[Kerbin]")
        "@Body[Kerbin]:NEEDS[Kopernicus]" -> ("@", "Body[Kerbin]")
        "Body"              -> ("", "Body")
    """
    modifier = ""
    if name and name[0] in "@!+-%":
        modifier = name[0]
        name = name[1:]
    # Strip :SUFFIX pass tags (e.g. :FINAL, :BEFORE[x], :AFTER[x], :NEEDS[x])
    colon_idx = name.find(":")
    if colon_idx != -1:
        name = name[:colon_idx]
    return modifier, name


def parse_config_node(text: str) -> ConfigNode:
    """Parse KSP ConfigNode text into a ConfigNode tree.

    KSP ConfigNode テキストをパースしてツリーを構築する。
    不正な行はスキップし warning を出す。クラッシュしない。

    Args:
        text: Raw .cfg file content.

    Returns:
        Root ConfigNode containing all parsed data.
    """
    # Remove comments
    text = _COMMENT_RE.sub("", text)
    lines = text.splitlines()

    root = ConfigNode()
    stack: list[ConfigNode] = [root]
    pending_name = ""

    for line_num, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line:
            continue

        if line == "{":
            mod, clean = _strip_modifier(pending_name)
            new_node = ConfigNode(name=clean, modifier=mod)
            stack[-1].children.append(new_node)
            stack.append(new_node)
            pending_name = ""
        elif line == "}":
            if len(stack) > 1:
                stack.pop()
            else:
                warnings.warn(
                    f"Line {line_num}: unmatched closing brace",
                    stacklevel=2,
                )
        elif "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Strip modifier from key for storage
            _, clean_key = _strip_modifier(key)
            stack[-1].values.append((clean_key, value))
            pending_name = ""
        elif line.endswith("{"):
            # "NodeName {" on same line
            name_part = line[:-1].strip()
            mod, clean = _strip_modifier(name_part)
            new_node = ConfigNode(name=clean, modifier=mod)
            stack[-1].children.append(new_node)
            stack.append(new_node)
            pending_name = ""
        elif line.endswith("}") and "{" in line:
            # "NodeName { }" on same line (empty block)
            name_part = line.split("{")[0].strip()
            mod, clean = _strip_modifier(name_part)
            new_node = ConfigNode(name=clean, modifier=mod)
            stack[-1].children.append(new_node)
            pending_name = ""
        else:
            # Could be a node name on its own line (next line should be {)
            pending_name = line

    return root
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_parser.py::TestConfigNodeParser -v
```

Expected: all PASS

- [ ] **Step 5: ruff + mypy**

```bash
ruff check kopdeltav/parser.py && ruff format kopdeltav/parser.py && mypy --strict kopdeltav/parser.py
```

- [ ] **Step 6: Commit**

```bash
git add kopdeltav/parser.py tests/test_parser.py
git commit -m "feat(parser): add ConfigNode tokenizer and parser"
```

---

### Task 5: parser.py — Body Extraction, Curve Parsing, Patch Application

**Files:**
- Modify: `kopdeltav/parser.py`
- Modify: `tests/test_parser.py`

- [ ] **Step 1: Write failing tests for body extraction**

Append to `tests/test_parser.py`:
```python
from kopdeltav.parser import parse_config, ParseResult
from kopdeltav.models import CurveKey


class TestCurveKeyParsing:
    def test_four_values(self) -> None:
        """key = position value inTangent outTangent"""
        from kopdeltav.parser import _parse_curve_key
        ck = _parse_curve_key("0 101.325 0 0")
        assert ck is not None
        assert ck.position == 0.0
        assert ck.value == 101.325
        assert ck.in_tangent == 0.0
        assert ck.out_tangent == 0.0

    def test_three_values_out_copies_in(self) -> None:
        """outTangent omitted -> copy inTangent"""
        from kopdeltav.parser import _parse_curve_key
        ck = _parse_curve_key("100 50.0 -0.5")
        assert ck is not None
        assert ck.out_tangent == -0.5

    def test_two_values_zero_tangents(self) -> None:
        from kopdeltav.parser import _parse_curve_key
        ck = _parse_curve_key("100 50.0")
        assert ck is not None
        assert ck.in_tangent == 0.0
        assert ck.out_tangent == 0.0

    def test_invalid_returns_none(self) -> None:
        from kopdeltav.parser import _parse_curve_key
        assert _parse_curve_key("not a curve") is None


class TestBodyExtraction:
    def test_simple_body(self) -> None:
        cfg = """
        @Kopernicus:FINAL
        {
            Body
            {
                name = TestPlanet
                Properties
                {
                    radius = 500000
                    geeASL = 0.8
                    rotationPeriod = 21600
                }
            }
        }
        """
        result = parse_config(cfg)
        names = [b.name for b in result.bodies]
        assert "TestPlanet" in names

    def test_loc_tag_falls_back_to_name(self) -> None:
        cfg = """
        @Kopernicus:FINAL
        {
            Body
            {
                name = TestBody
                Properties
                {
                    displayName = #LOC_TestBody
                }
            }
        }
        """
        result = parse_config(cfg)
        body = next(b for b in result.bodies if b.name == "TestBody")
        assert body.display_name == "TestBody"

    def test_delete_directive_skipped(self) -> None:
        cfg = """
        @Kopernicus:FINAL
        {
            !Body[Kerbin] {}
        }
        """
        result = parse_config(cfg)
        # Should not crash, Kerbin removed from stock
        kerbin = next((b for b in result.bodies if b.name == "Kerbin"), None)
        assert kerbin is None

    def test_patch_modifies_stock(self) -> None:
        cfg = """
        @Kopernicus:FINAL
        {
            @Body[Kerbin]
            {
                @Properties
                {
                    radius = 700000
                }
            }
        }
        """
        result = parse_config(cfg)
        kerbin = next((b for b in result.bodies if b.name == "Kerbin"), None)
        assert kerbin is not None
        assert kerbin.radius == 700_000.0

    def test_broken_body_skipped_with_warning(self) -> None:
        cfg = """
        @Kopernicus:FINAL
        {
            Body
            {
                Properties
                {
                    geeASL = not_a_number
                }
            }
        }
        """
        result = parse_config(cfg)
        assert len(result.warnings) > 0

    def test_empty_config(self) -> None:
        result = parse_config("")
        # Should return stock bodies only
        assert len(result.bodies) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_parser.py::TestCurveKeyParsing tests/test_parser.py::TestBodyExtraction -v
```

Expected: FAIL

- [ ] **Step 3: Implement _parse_curve_key, body extraction, and parse_config**

Add to `kopdeltav/parser.py`:

```python
def _parse_curve_key(value_str: str) -> CurveKey | None:
    """Parse a curve key value string.

    カーブキー文字列をパースする。
    Format: "position value [inTangent [outTangent]]"
    outTangent omitted -> copies inTangent. Both omitted -> 0.

    Args:
        value_str: Space-separated values.

    Returns:
        CurveKey or None if parsing fails.
    """
    parts = value_str.split()
    try:
        if len(parts) >= 4:
            return CurveKey(float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))
        elif len(parts) == 3:
            in_t = float(parts[2])
            return CurveKey(float(parts[0]), float(parts[1]), in_t, in_t)
        elif len(parts) == 2:
            return CurveKey(float(parts[0]), float(parts[1]), 0.0, 0.0)
    except (ValueError, IndexError):
        pass
    return None


@dataclass
class ParseResult:
    """Result of parsing Kopernicus configs.

    パース結果。天体リストと警告メッセージ。

    Attributes:
        bodies: Parsed celestial bodies with parent-child links built.
        warnings: Warning messages from parsing.
    """
    bodies: list[CelestialBody]
    warnings: list[str]


def _extract_bracket_name(node_name: str) -> str | None:
    """Extract name from bracket syntax like 'Body[Kerbin]' -> 'Kerbin'.

    ブラケット構文からターゲット名を抽出する。

    Args:
        node_name: Node name potentially containing brackets.

    Returns:
        Extracted name, or None if no brackets found.
    """
    start = node_name.find("[")
    end = node_name.find("]")
    if start != -1 and end != -1 and end > start:
        return node_name[start + 1 : end]
    return None


def _extract_atmosphere(atmo_node: ConfigNode, warnings: list[str]) -> Atmosphere | None:
    """Extract Atmosphere from an Atmosphere ConfigNode.

    Atmosphere ConfigNode から Atmosphere を抽出する。
    """
    depth_str = atmo_node.get_value("atmosphereDepth") or atmo_node.get_value("maxAltitude")
    if depth_str is None:
        return None

    try:
        depth = float(depth_str)
    except ValueError:
        warnings.append(f"Invalid atmosphereDepth: {depth_str}")
        return None

    def _get_float(key: str, default: float = 0.0) -> float:
        val = atmo_node.get_value(key)
        if val is None:
            return default
        try:
            return float(val)
        except ValueError:
            warnings.append(f"Invalid {key}: {val}")
            return default

    # Parse pressure and temperature curves
    pressure_keys: list[CurveKey] = []
    temp_keys: list[CurveKey] = []

    for sub in atmo_node.children:
        if sub.name in ("pressureCurve", "temperatureCurve"):
            keys_list = pressure_keys if sub.name == "pressureCurve" else temp_keys
            for _, val in sub.values:
                if val.strip():
                    ck = _parse_curve_key(val)
                    if ck is not None:
                        keys_list.append(ck)
                    else:
                        warnings.append(f"Invalid curve key in {sub.name}: {val}")

    return Atmosphere(
        atmosphere_depth=depth,
        pressure_curve=sorted(pressure_keys, key=lambda k: k.position),
        temperature_curve=sorted(temp_keys, key=lambda k: k.position),
        molar_mass=_get_float("atmosphereMolarMass", 0.029),
        adiabatic_index=_get_float("atmosphereAdiabaticIndex", 1.4),
        pressure_at_sea_level=_get_float("staticPressureASL", 101.325),
        temperature_at_sea_level=_get_float("temperatureSeaLevel", 288.0),
    )


def _extract_orbit(orbit_node: ConfigNode, warnings: list[str]) -> OrbitalElements | None:
    """Extract OrbitalElements from an Orbit ConfigNode.

    Orbit ConfigNode から OrbitalElements を抽出する。
    """
    def _get_float(key: str, default: float = 0.0) -> float:
        val = orbit_node.get_value(key)
        if val is None:
            return default
        try:
            return float(val)
        except ValueError:
            warnings.append(f"Invalid orbit {key}: {val}")
            return default

    sma = _get_float("semiMajorAxis")
    if sma == 0.0:
        return None

    return OrbitalElements(
        semi_major_axis=sma,
        eccentricity=_get_float("eccentricity"),
        inclination=_get_float("inclination"),
        argument_of_periapsis=_get_float("argumentOfPeriapsis"),
        longitude_of_ascending_node=_get_float("longitudeOfAscendingNode"),
        mean_anomaly_at_epoch=_get_float("meanAnomalyAtEpoch"),
        epoch=_get_float("epoch"),
    )


def _extract_body(node: ConfigNode, warnings: list[str]) -> CelestialBody | None:
    """Extract a CelestialBody from a Body ConfigNode.

    Body ConfigNode から CelestialBody を抽出する。
    必須フィールド (name) が欠けている場合は None を返す。

    Args:
        node: A ConfigNode whose name is "Body" (new body).
        warnings: Mutable list to append warnings to.

    Returns:
        CelestialBody or None on failure.
    """
    name = node.get_value("name")
    if name is None:
        warnings.append("Body without name, skipping")
        return None

    # Properties sub-node (may be at body level or nested)
    props_nodes = node.get_nodes("Properties")
    props = props_nodes[0] if props_nodes else node

    def _get_float(key: str, default: float = 0.0) -> float:
        val = props.get_value(key)
        if val is None:
            val = node.get_value(key)
        if val is None:
            return default
        try:
            return float(val)
        except ValueError:
            warnings.append(f"Invalid {key} for {name}: {val}")
            return default

    radius = _get_float("radius", 0.0)
    gee_asl = _get_float("geeASL", 0.0)
    if radius == 0 or gee_asl == 0:
        warnings.append(f"Body {name} missing radius or geeASL, skipping")
        return None

    rotation_period = _get_float("rotationPeriod", 21600.0)
    has_ocean = props.get_value("ocean") == "True"

    display_name_raw = props.get_value("displayName") or name
    display_name = name if display_name_raw.startswith("#LOC_") else display_name_raw

    soi = _get_float("sphereOfInfluence", 0.0)

    # Orbit
    orbit: OrbitalElements | None = None
    orbit_nodes = node.get_nodes("Orbit")
    if orbit_nodes:
        orbit = _extract_orbit(orbit_nodes[0], warnings)

    # Atmosphere
    atmosphere: Atmosphere | None = None
    atmo_nodes = node.get_nodes("Atmosphere")
    if atmo_nodes:
        atmosphere = _extract_atmosphere(atmo_nodes[0], warnings)

    return CelestialBody(
        name=name,
        radius=radius,
        gee_asl=gee_asl,
        has_ocean=has_ocean,
        atmosphere=atmosphere,
        orbit=orbit,
        rotational_period=rotation_period,
        display_name=display_name,
        soi=soi,
    )


def _apply_patch(body: CelestialBody, patch_node: ConfigNode, warnings: list[str]) -> None:
    """Apply a @Body[Name] patch to an existing CelestialBody.

    パッチノードのプロパティで既存天体を上書き更新する。

    Mutates body in-place. Only overwrites fields present in the patch.
    """
    props_nodes = patch_node.get_nodes("Properties")
    props = props_nodes[0] if props_nodes else patch_node

    for key, val in props.values:
        try:
            if key == "radius":
                body.radius = float(val)
                body.mu = compute_mu(body.gee_asl, body.radius)
            elif key == "geeASL":
                body.gee_asl = float(val)
                body.mu = compute_mu(body.gee_asl, body.radius)
            elif key == "rotationPeriod":
                body.rotational_period = float(val)
            elif key == "displayName":
                body.display_name = body.name if val.startswith("#LOC_") else val
            elif key == "ocean":
                body.has_ocean = val == "True"
            elif key == "sphereOfInfluence":
                body.soi = float(val)
        except ValueError:
            warnings.append(f"Invalid patch value {key}={val} for {body.name}")

    # Patch orbit if present
    orbit_nodes = patch_node.get_nodes("Orbit")
    if orbit_nodes:
        body.orbit = _extract_orbit(orbit_nodes[0], warnings)

    # Patch atmosphere if present
    atmo_nodes = patch_node.get_nodes("Atmosphere")
    if atmo_nodes:
        body.atmosphere = _extract_atmosphere(atmo_nodes[0], warnings)


def _deep_copy_tree(root: CelestialBody) -> CelestialBody:
    """Deep copy a celestial body tree to avoid mutating cached stock data.

    キャッシュされた Stock データを変更しないようにツリーを深コピーする。
    """
    import copy
    # Temporarily break parent refs to avoid infinite recursion in deepcopy
    bodies: list[CelestialBody] = []

    def _collect(body: CelestialBody) -> None:
        bodies.append(body)
        for child in body.children:
            _collect(child)

    _collect(root)
    old_parents = {id(b): b.parent for b in bodies}
    for b in bodies:
        b.parent = None

    new_root = copy.deepcopy(root)

    # Restore original parents
    for b in bodies:
        b.parent = old_parents[id(b)]

    # Re-link parents in copied tree
    def _relink(body: CelestialBody) -> None:
        for child in body.children:
            child.parent = body
            _relink(child)

    _relink(new_root)
    return new_root


def _flatten_tree(root: CelestialBody) -> dict[str, CelestialBody]:
    """Flatten a celestial body tree into a name->body dict.

    天体ツリーを名前→天体の辞書にフラット化する。
    """
    result: dict[str, CelestialBody] = {}

    def _walk(body: CelestialBody) -> None:
        result[body.name] = body
        for child in body.children:
            _walk(child)

    _walk(root)
    return result


def parse_config(
    text: str,
    stock_bodies: list[CelestialBody] | None = None,
) -> ParseResult:
    """Parse Kopernicus config text with stock body base.

    Kopernicus config をパースし、Stock 天体をベースにパッチを適用する。

    Processing order:
    1. Load stock bodies as base (deep-copied to avoid mutating cache)
    2. Parse all new Body {} definitions -> add
    3. Apply @Body[Name] {} patches -> modify
    4. Apply !Body[Name] {} deletions -> remove

    Args:
        text: .cfg file content.
        stock_bodies: Base stock bodies (auto-loaded if None).

    Returns:
        ParseResult with bodies and warnings.
    """
    from kopdeltav.stock import get_stock_system

    warn: list[str] = []

    # 1. Load and deep-copy stock as base
    if stock_bodies is not None:
        body_dict: dict[str, CelestialBody] = {b.name: b for b in stock_bodies}
    else:
        stock_root = _deep_copy_tree(get_stock_system())
        body_dict = _flatten_tree(stock_root)

    # Parse the config text
    root_node = parse_config_node(text)

    # Find Kopernicus blocks (may also be at root level)
    kop_nodes = root_node.get_nodes("Kopernicus")
    if not kop_nodes:
        # No Kopernicus block — return stock as-is
        return ParseResult(bodies=list(body_dict.values()), warnings=warn)

    # Collect operations from all Kopernicus blocks
    new_body_nodes: list[ConfigNode] = []
    patch_nodes: list[ConfigNode] = []
    delete_names: list[str] = []

    for kop in kop_nodes:
        for child in kop.children:
            base_name = child.name.split("[")[0] if "[" in child.name else child.name
            if base_name == "Body":
                if child.modifier == "!":
                    # Deletion directive
                    target = _extract_bracket_name(child.name)
                    if target:
                        delete_names.append(target)
                    else:
                        warn.append(f"Delete directive without target: {child.name}")
                elif child.modifier == "@":
                    # Patch
                    patch_nodes.append(child)
                else:
                    # New body definition
                    new_body_nodes.append(child)

    # 2. Phase: new Body definitions
    for node in new_body_nodes:
        body = _extract_body(node, warn)
        if body is not None:
            body_dict[body.name] = body

    # 3. Phase: @Body[Name] patches
    for node in patch_nodes:
        target_name = _extract_bracket_name(node.name)
        if target_name and target_name in body_dict:
            _apply_patch(body_dict[target_name], node, warn)
        elif target_name:
            warn.append(f"Patch target not found: {target_name}")

    # 4. Phase: !Body[Name] deletions
    for name in delete_names:
        if name in body_dict:
            del body_dict[name]
        else:
            warn.append(f"Delete target not found: {name}")

    return ParseResult(bodies=list(body_dict.values()), warnings=warn)


def parse_gamedata(gamedata_path: Path) -> ParseResult:
    """Scan GameData folder and parse all Kopernicus configs.

    GameData フォルダを再帰スキャンし、全 Kopernicus config をパースする。
    Stock 天体をベースとし、Kopernicus パッチを適用した完全な天体ツリーを返す。

    Processing: concatenates all discovered .cfg files, then parses as one config.
    This ensures correct ordering (new bodies before patches before deletions).

    Args:
        gamedata_path: Path to GameData directory.

    Returns:
        Merged ParseResult with all bodies and warnings.
    """
    from kopdeltav.discovery import scan_kopernicus_configs

    configs = scan_kopernicus_configs(gamedata_path)
    if not configs:
        # No Kopernicus configs — return stock system
        from kopdeltav.stock import get_stock_system
        stock_root = _deep_copy_tree(get_stock_system())
        return ParseResult(bodies=list(_flatten_tree(stock_root).values()), warnings=[])

    # Concatenate all config files
    combined = ""
    for cfg_path in configs:
        try:
            combined += cfg_path.read_text(encoding="utf-8", errors="replace") + "\n"
        except OSError as e:
            pass  # scan already validated readability

    return parse_config(combined)
```

The full implementation must handle:
- Loading stock system as base (flatten tree to dict by name)
- Phase 1: new `Body {}` definitions
- Phase 2: `@Body[Name] {}` patches (merge properties)
- Phase 3: `!Body[Name] {}` deletions
- Rebuild parent-child tree from flat dict
- Return ParseResult

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_parser.py -v
```

Expected: all PASS

- [ ] **Step 5: ruff + mypy**

```bash
ruff check kopdeltav/parser.py && ruff format kopdeltav/parser.py && mypy --strict kopdeltav/parser.py
```

- [ ] **Step 6: Commit**

```bash
git add kopdeltav/parser.py tests/test_parser.py
git commit -m "feat(parser): add body extraction, curve parsing, and patch application"
```

---

### Task 6: parser.py — Test Against Sanctar.cfg

**Files:**
- Modify: `tests/test_parser.py`
- Requires: `sample_configs/Sanctar.cfg`

- [ ] **Step 1: Write Sanctar.cfg integration test**

Append to `tests/test_parser.py`:
```python
import math
from pathlib import Path

SAMPLE_DIR = Path(__file__).parent.parent / "sample_configs"


class TestSanctarParsing:
    def test_sanctar_cfg_exists(self) -> None:
        assert (SAMPLE_DIR / "Sanctar.cfg").exists()

    def test_parse_sanctar(self) -> None:
        text = (SAMPLE_DIR / "Sanctar.cfg").read_text(encoding="utf-8")
        result = parse_config(text)
        names = [b.name for b in result.bodies]
        assert "Sanctar" in names

    def test_sanctar_radius(self) -> None:
        text = (SAMPLE_DIR / "Sanctar.cfg").read_text(encoding="utf-8")
        result = parse_config(text)
        sanctar = next(b for b in result.bodies if b.name == "Sanctar")
        assert sanctar.radius == 670_000.0

    def test_sanctar_gee(self) -> None:
        text = (SAMPLE_DIR / "Sanctar.cfg").read_text(encoding="utf-8")
        result = parse_config(text)
        sanctar = next(b for b in result.bodies if b.name == "Sanctar")
        assert math.isclose(sanctar.gee_asl, 1.1, rel_tol=1e-3)

    def test_sanctar_mu(self) -> None:
        text = (SAMPLE_DIR / "Sanctar.cfg").read_text(encoding="utf-8")
        result = parse_config(text)
        sanctar = next(b for b in result.bodies if b.name == "Sanctar")
        assert math.isclose(sanctar.mu, 4.8424e12, rel_tol=1e-3)

    def test_sanctar_has_atmosphere(self) -> None:
        text = (SAMPLE_DIR / "Sanctar.cfg").read_text(encoding="utf-8")
        result = parse_config(text)
        sanctar = next(b for b in result.bodies if b.name == "Sanctar")
        assert sanctar.atmosphere is not None

    def test_no_warnings_for_sanctar(self) -> None:
        text = (SAMPLE_DIR / "Sanctar.cfg").read_text(encoding="utf-8")
        result = parse_config(text)
        # Well-formed config should produce no warnings
        assert len(result.warnings) == 0
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_parser.py::TestSanctarParsing -v
```

Expected: PASS (if Sanctar.cfg is present and parser is correct)

- [ ] **Step 3: Fix any issues found**

Iterate until all Sanctar tests pass. This validates the parser against real Kopernicus config data.

- [ ] **Step 4: Commit**

```bash
git add tests/test_parser.py
git commit -m "test(parser): add Sanctar.cfg integration tests"
```

---

### Task 7: discovery.py — GameData Path Discovery

**Files:**
- Create: `kopdeltav/discovery.py`
- Create: `tests/test_discovery.py`

- [ ] **Step 1: Write failing tests**

`tests/test_discovery.py`:
```python
from __future__ import annotations

from pathlib import Path

import pytest

from kopdeltav.discovery import find_gamedata, scan_kopernicus_configs


class TestFindGamedata:
    def test_explicit_gamedata_path(self, tmp_path: Path) -> None:
        gd = tmp_path / "GameData"
        gd.mkdir()
        assert find_gamedata(gd) == gd

    def test_explicit_ksp_install_path(self, tmp_path: Path) -> None:
        """Passing KSP root auto-appends /GameData."""
        gd = tmp_path / "GameData"
        gd.mkdir()
        assert find_gamedata(tmp_path) == gd

    def test_nonexistent_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            find_gamedata(tmp_path / "nonexistent")

    def test_path_without_gamedata_raises(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(FileNotFoundError):
            find_gamedata(empty)


class TestScanKopernicusConfigs:
    def test_finds_kopernicus_cfg(self, tmp_path: Path) -> None:
        gd = tmp_path / "GameData"
        mod_dir = gd / "MyPlanetPack"
        mod_dir.mkdir(parents=True)
        cfg = mod_dir / "planets.cfg"
        cfg.write_text("@Kopernicus:FINAL\n{\n    Body { name = Test }\n}\n")
        result = scan_kopernicus_configs(gd)
        assert len(result) == 1
        assert result[0] == cfg

    def test_ignores_non_kopernicus_cfg(self, tmp_path: Path) -> None:
        gd = tmp_path / "GameData"
        mod_dir = gd / "SomePart"
        mod_dir.mkdir(parents=True)
        cfg = mod_dir / "part.cfg"
        cfg.write_text("PART { name = myPart }\n")
        result = scan_kopernicus_configs(gd)
        assert len(result) == 0

    def test_ignores_non_cfg_files(self, tmp_path: Path) -> None:
        gd = tmp_path / "GameData"
        gd.mkdir()
        txt = gd / "readme.txt"
        txt.write_text("Kopernicus stuff")
        result = scan_kopernicus_configs(gd)
        assert len(result) == 0

    def test_recursive_scan(self, tmp_path: Path) -> None:
        gd = tmp_path / "GameData"
        deep = gd / "Mods" / "Pack" / "Bodies"
        deep.mkdir(parents=True)
        cfg = deep / "star.cfg"
        cfg.write_text("Kopernicus\n{\n    Body { name = Star }\n}\n")
        result = scan_kopernicus_configs(gd)
        assert len(result) == 1

    def test_skips_large_files(self, tmp_path: Path) -> None:
        gd = tmp_path / "GameData"
        gd.mkdir()
        big = gd / "huge.cfg"
        big.write_text("Kopernicus\n" + "x" * (1024 * 1024 + 1))
        result = scan_kopernicus_configs(gd)
        assert len(result) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_discovery.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement discovery.py**

```python
"""GameData path discovery and Kopernicus config scanner.

GameData フォルダのパス解決と Kopernicus config 検出。
"""
from __future__ import annotations

import sys
from pathlib import Path

_MAX_CFG_SIZE = 1024 * 1024  # 1 MB

_STEAM_RELATIVE = Path("steamapps/common/Kerbal Space Program/GameData")

_DEFAULT_PATHS: list[Path] = []


def _build_default_paths() -> list[Path]:
    """Build platform-specific default Steam paths.

    プラットフォーム別のデフォルト Steam パスを構築する。
    """
    paths: list[Path] = []
    if sys.platform == "win32":
        paths.append(Path("C:/Program Files (x86)/Steam") / _STEAM_RELATIVE)
    elif sys.platform == "darwin":
        paths.append(Path.home() / "Library/Application Support/Steam" / _STEAM_RELATIVE)
    else:  # Linux
        paths.append(Path.home() / ".steam/steam" / _STEAM_RELATIVE)
        paths.append(Path.home() / ".local/share/Steam" / _STEAM_RELATIVE)
    return paths


def find_gamedata(user_path: Path | None = None) -> Path:
    """Resolve the GameData directory path.

    GameData ディレクトリのパスを解決する。

    Resolution order:
    1. user_path if provided (accepts GameData dir or KSP install dir)
    2. Platform-specific Steam default paths

    Args:
        user_path: User-specified path (optional).

    Returns:
        Path to GameData directory.

    Raises:
        FileNotFoundError: If GameData directory cannot be found.
    """
    if user_path is not None:
        if not user_path.exists():
            raise FileNotFoundError(f"Path does not exist: {user_path}")
        if user_path.name == "GameData" and user_path.is_dir():
            return user_path
        candidate = user_path / "GameData"
        if candidate.is_dir():
            return candidate
        raise FileNotFoundError(f"GameData not found in: {user_path}")

    for path in _build_default_paths():
        if path.is_dir():
            return path

    raise FileNotFoundError(
        "GameData directory not found. Please specify the path explicitly."
    )


def scan_kopernicus_configs(gamedata_path: Path) -> list[Path]:
    """Recursively scan GameData for Kopernicus config files.

    GameData 以下を再帰スキャンし、Kopernicus 定義を含む .cfg を返す。

    Filters by file content: only files containing 'Kopernicus' block.
    Skips files larger than 1 MB.

    Args:
        gamedata_path: Path to GameData directory.

    Returns:
        List of paths to Kopernicus .cfg files.
    """
    results: list[Path] = []
    for cfg_path in gamedata_path.rglob("*.cfg"):
        if not cfg_path.is_file():
            continue
        if cfg_path.stat().st_size > _MAX_CFG_SIZE:
            continue
        try:
            content = cfg_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Check for Kopernicus block (with or without modifier prefix)
        if "Kopernicus" in content:
            results.append(cfg_path)
    return results
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_discovery.py -v
```

Expected: all PASS

- [ ] **Step 5: ruff + mypy**

```bash
ruff check kopdeltav/discovery.py && ruff format kopdeltav/discovery.py && mypy --strict kopdeltav/discovery.py
```

- [ ] **Step 6: Commit**

```bash
git add kopdeltav/discovery.py tests/test_discovery.py
git commit -m "feat(discovery): add GameData path resolution and Kopernicus config scanner"
```

---

### Task 8: calculator.py — Core Orbital Mechanics

**Files:**
- Create: `kopdeltav/calculator.py`
- Create: `tests/test_calculator.py`

- [ ] **Step 1: Write failing tests for basic orbital functions**

`tests/test_calculator.py`:
```python
from __future__ import annotations

import math

from kopdeltav.calculator import (
    atmospheric_density,
    circular_velocity,
    escape_velocity,
)
from kopdeltav.models import Atmosphere, CelestialBody, CurveKey, G0


def _make_body(
    name: str = "Test",
    radius: float = 600_000.0,
    gee_asl: float = 1.0,
    atmosphere: Atmosphere | None = None,
    rotational_period: float = 21_600.0,
) -> CelestialBody:
    return CelestialBody(
        name=name,
        radius=radius,
        gee_asl=gee_asl,
        has_ocean=False,
        atmosphere=atmosphere,
        orbit=None,
        rotational_period=rotational_period,
        display_name=name,
    )


class TestCircularVelocity:
    def test_kerbin_lko(self) -> None:
        """Kerbin 80km orbit: v ~= 2279 m/s"""
        body = _make_body()
        v = circular_velocity(body, 80_000.0)
        assert math.isclose(v, 2279.0, rel_tol=0.01)

    def test_sanctar_80km(self) -> None:
        """Sanctar 80km: v ~= 2541.1 m/s (reference value)"""
        body = _make_body(radius=670_000.0, gee_asl=1.1)
        v = circular_velocity(body, 80_000.0)
        assert math.isclose(v, 2541.1, rel_tol=0.01)

    def test_negative_altitude_raises(self) -> None:
        body = _make_body()
        import pytest
        with pytest.raises(ValueError):
            circular_velocity(body, -100.0)


class TestEscapeVelocity:
    def test_sanctar_surface(self) -> None:
        """Sanctar surface escape: ~3802 m/s (reference value)"""
        body = _make_body(radius=670_000.0, gee_asl=1.1)
        v = escape_velocity(body, 0.0)
        assert math.isclose(v, 3802.0, rel_tol=0.01)

    def test_escape_is_sqrt2_times_circular(self) -> None:
        body = _make_body()
        vc = circular_velocity(body, 100_000.0)
        ve = escape_velocity(body, 100_000.0)
        assert math.isclose(ve, vc * math.sqrt(2), rel_tol=1e-9)


class TestAtmosphericDensity:
    def test_sea_level_density(self) -> None:
        """ρ = P*1000*M / (R*T) at sea level."""
        atmo = Atmosphere(
            atmosphere_depth=70_000.0,
            pressure_curve=[CurveKey(0.0, 101.325, 0.0, 0.0)],
            temperature_curve=[CurveKey(0.0, 288.15, 0.0, 0.0)],
            molar_mass=0.029,
            adiabatic_index=1.4,
            pressure_at_sea_level=101.325,
            temperature_at_sea_level=288.15,
        )
        rho = atmospheric_density(atmo, 0.0)
        expected = 101.325 * 1000 * 0.029 / (8.314462 * 288.15)
        assert math.isclose(rho, expected, rel_tol=1e-6)

    # Sanctar sea-level density tested in Task 10 (TestSanctarRegression)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_calculator.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement core orbital functions**

```python
"""Delta-V calculation engine.

軌道力学の計算エンジン。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from kopdeltav.models import (
    Atmosphere,
    CelestialBody,
    G0,
    hermite_interp,
)

R_UNIVERSAL: float = 8.314462  # Universal gas constant [J/(mol*K)]


def circular_velocity(body: CelestialBody, altitude: float) -> float:
    """Circular orbital velocity at given altitude [m/s].

    指定高度での円軌道速度。v = sqrt(mu / r).

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
    """Escape velocity at given altitude [m/s].

    指定高度での脱出速度。v = sqrt(2*mu / r).

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


def atmospheric_density(atmosphere: Atmosphere, altitude: float) -> float:
    """Atmospheric density at given altitude [kg/m^3].

    指定高度での大気密度。理想気体の式 rho = P*1000*M / (R*T)。
    Pressure from Hermite interpolation of pressure_curve [kPa -> Pa with *1000].

    Args:
        atmosphere: Atmospheric parameters.
        altitude: Altitude above surface [m].

    Returns:
        Density [kg/m^3]. Returns 0 if above atmosphere_depth.
    """
    if altitude >= atmosphere.atmosphere_depth:
        return 0.0

    pressure_kpa = hermite_interp(atmosphere.pressure_curve, altitude)
    temperature = hermite_interp(atmosphere.temperature_curve, altitude)

    if temperature <= 0 or pressure_kpa <= 0:
        return 0.0

    # kPa -> Pa conversion: *1000
    return (pressure_kpa * 1000.0) * atmosphere.molar_mass / (R_UNIVERSAL * temperature)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_calculator.py -v
```

Expected: PASS

- [ ] **Step 5: ruff + mypy**

```bash
ruff check kopdeltav/calculator.py && ruff format kopdeltav/calculator.py && mypy --strict kopdeltav/calculator.py
```

- [ ] **Step 6: Commit**

```bash
git add kopdeltav/calculator.py tests/test_calculator.py
git commit -m "feat(calculator): add circular_velocity, escape_velocity, atmospheric_density"
```

---

### Task 9: calculator.py — Launch ΔV, Hohmann, Tsiolkovsky

**Files:**
- Modify: `kopdeltav/calculator.py`
- Modify: `tests/test_calculator.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_calculator.py`:
```python
from kopdeltav.calculator import (
    hohmann_transfer,
    launch_to_orbit,
    tsiolkovsky,
    LaunchResult,
    HohmannResult,
    TsiolkovskyResult,
)
from kopdeltav.stock import get_stock_body

import pytest


class TestLaunchToOrbit:
    def test_sanctar_rocket_dv(self) -> None:
        """Sanctar 80km: total_rocket ~3110 m/s (reference)."""
        body = _make_body(
            name="Sanctar", radius=670_000.0, gee_asl=1.1,
            rotational_period=28_800.0,
            # Needs atmosphere for full test — placeholder here
        )
        result = launch_to_orbit(body, 80_000.0)
        # Without atmosphere data, just check structure
        assert result.orbital_velocity > 0
        assert result.total_rocket_dv > result.orbital_velocity

    def test_airless_body_no_drag(self) -> None:
        body = _make_body()
        result = launch_to_orbit(body, 80_000.0)
        assert result.drag_loss == 0.0
        assert result.jet_saving == 0.0


class TestHohmannTransfer:
    def test_same_parent_required(self) -> None:
        kerbin = get_stock_body("Kerbin")
        laythe = get_stock_body("Laythe")
        assert kerbin is not None and laythe is not None
        with pytest.raises(ValueError):
            hohmann_transfer(kerbin, laythe, 80_000.0, 50_000.0)

    def test_kerbin_to_duna(self) -> None:
        kerbin = get_stock_body("Kerbin")
        duna = get_stock_body("Duna")
        assert kerbin is not None and duna is not None
        result = hohmann_transfer(kerbin, duna, 80_000.0, 60_000.0)
        assert result.total_dv > 0
        assert result.transfer_time > 0
        # Known approximate: ~1080 m/s departure from Kerbin orbit
        assert math.isclose(result.departure_dv, 1080.0, rel_tol=0.1)


class TestTsiolkovsky:
    def test_known_mass_ratio(self) -> None:
        """dv=2000, isp=300, g0=9.80665 -> mass_ratio = e^(2000/2942) ~1.973"""
        result = tsiolkovsky(delta_v=2000.0, isp=300.0, dry_mass=1000.0)
        expected_ratio = math.exp(2000.0 / (300.0 * G0))
        assert math.isclose(result.mass_ratio, expected_ratio, rel_tol=1e-6)

    def test_fuel_mass(self) -> None:
        result = tsiolkovsky(delta_v=2000.0, isp=300.0, dry_mass=1000.0)
        assert math.isclose(result.wet_mass, result.mass_ratio * 1000.0, rel_tol=1e-6)
        assert math.isclose(result.fuel_mass, result.wet_mass - 1000.0, rel_tol=1e-6)

    def test_zero_dv(self) -> None:
        result = tsiolkovsky(delta_v=0.0, isp=300.0, dry_mass=1000.0)
        assert result.mass_ratio == 1.0
        assert result.fuel_mass == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_calculator.py -v -k "Launch or Hohmann or Tsiolkovsky"
```

Expected: FAIL

- [ ] **Step 3: Implement launch_to_orbit, hohmann_transfer, tsiolkovsky**

Add to `kopdeltav/calculator.py`:

```python
@dataclass
class LaunchResult:
    """Launch-to-orbit Delta-V calculation result.

    低軌道投入 ΔV の計算結果。
    """
    orbital_velocity: float
    surface_velocity: float
    theoretical_dv: float
    gravity_loss: float
    drag_loss: float
    total_rocket_dv: float
    jet_saving: float
    total_jet_dv: float


def launch_to_orbit(body: CelestialBody, target_altitude: float) -> LaunchResult:
    """Calculate launch-to-orbit Delta-V.

    低軌道投入 ΔV を計算する。赤道打ち上げ（緯度 0°）を想定。

    Empirical estimates:
    - gravity_loss ~ surface_g * (orbital_v / (1.5 * g0))  (TWR=1.5 assumed)
    - drag_loss ~ 0.1 * orbital_v  (atmospheric bodies only)
    - jet_saving ~ 0.36 * orbital_v  (sufficient atmosphere only)

    Error margin: 5-15% vs actual in-game values.

    Args:
        body: Target celestial body.
        target_altitude: Target orbit altitude [m].

    Returns:
        LaunchResult with all ΔV components.
    """
    orbital_v = circular_velocity(body, target_altitude)
    surface_v = 2.0 * math.pi * body.radius / body.rotational_period if body.rotational_period > 0 else 0.0
    theoretical = orbital_v - surface_v

    surface_g = body.gee_asl * G0
    burn_time = orbital_v / (1.5 * G0)
    gravity_loss = surface_g * burn_time * 0.15  # empirical factor

    has_atmo = body.atmosphere is not None
    drag_loss = 0.1 * orbital_v if has_atmo else 0.0
    jet_saving = 0.36 * orbital_v if has_atmo else 0.0

    total_rocket = theoretical + gravity_loss + drag_loss
    total_jet = total_rocket - jet_saving

    return LaunchResult(
        orbital_velocity=orbital_v,
        surface_velocity=surface_v,
        theoretical_dv=theoretical,
        gravity_loss=gravity_loss,
        drag_loss=drag_loss,
        total_rocket_dv=total_rocket,
        jet_saving=jet_saving,
        total_jet_dv=total_jet,
    )


@dataclass
class HohmannResult:
    """Hohmann transfer calculation result.

    ホーマン遷移の計算結果。
    """
    departure_dv: float
    arrival_dv: float
    total_dv: float
    transfer_time: float
    ejection_dv: float


def hohmann_transfer(
    body_from: CelestialBody,
    body_to: CelestialBody,
    parking_altitude_from: float,
    parking_altitude_to: float,
) -> HohmannResult:
    """Calculate Hohmann transfer between two bodies orbiting the same parent.

    同一親天体を周回する 2 天体間のホーマン遷移 ΔV。

    Args:
        body_from: Departure body.
        body_to: Arrival body.
        parking_altitude_from: Parking orbit altitude at departure [m].
        parking_altitude_to: Parking orbit altitude at arrival [m].

    Returns:
        HohmannResult.

    Raises:
        ValueError: If bodies don't share the same parent.
    """
    if body_from.parent is None or body_to.parent is None:
        raise ValueError("Both bodies must have a parent for Hohmann transfer")
    if body_from.parent.name != body_to.parent.name:
        raise ValueError(
            f"Bodies must share same parent: {body_from.name} orbits "
            f"{body_from.parent.name}, {body_to.name} orbits {body_to.parent.name}"
        )

    parent = body_from.parent

    # Orbital radii (SMA of bodies around parent)
    r1 = body_from.orbit.semi_major_axis if body_from.orbit else 0.0
    r2 = body_to.orbit.semi_major_axis if body_to.orbit else 0.0
    if r1 == 0 or r2 == 0:
        raise ValueError("Both bodies must have orbital elements")

    # Transfer orbit semi-major axis
    a_transfer = (r1 + r2) / 2.0

    # Velocities in parent's frame
    v1_circular = math.sqrt(parent.mu / r1)
    v2_circular = math.sqrt(parent.mu / r2)
    v1_transfer = math.sqrt(parent.mu * (2.0 / r1 - 1.0 / a_transfer))
    v2_transfer = math.sqrt(parent.mu * (2.0 / r2 - 1.0 / a_transfer))

    departure_dv = abs(v1_transfer - v1_circular)
    arrival_dv = abs(v2_circular - v2_transfer)

    # Transfer time (half period of transfer orbit)
    transfer_time = math.pi * math.sqrt(a_transfer**3 / parent.mu)

    # Ejection from parking orbit (Oberth effect)
    r_park = body_from.radius + parking_altitude_from
    v_park = math.sqrt(body_from.mu / r_park)
    v_inf = departure_dv  # hyperbolic excess
    v_ejection = math.sqrt(v_inf**2 + 2.0 * body_from.mu / r_park)
    ejection_dv = v_ejection - v_park

    return HohmannResult(
        departure_dv=departure_dv,
        arrival_dv=arrival_dv,
        total_dv=departure_dv + arrival_dv,
        transfer_time=transfer_time,
        ejection_dv=ejection_dv,
    )


@dataclass
class TsiolkovskyResult:
    """Tsiolkovsky rocket equation result.

    ツィオルコフスキーの公式の計算結果。
    """
    mass_ratio: float
    fuel_fraction: float
    wet_mass: float
    fuel_mass: float


def tsiolkovsky(delta_v: float, isp: float, dry_mass: float) -> TsiolkovskyResult:
    """Calculate mass ratio using Tsiolkovsky rocket equation.

    ツィオルコフスキーの公式で質量比を計算する。
    mass_ratio = exp(dv / (isp * g0))

    Args:
        delta_v: Required delta-v [m/s].
        isp: Specific impulse [s].
        dry_mass: Dry mass [kg].

    Returns:
        TsiolkovskyResult.
    """
    ve = isp * G0
    mass_ratio = math.exp(delta_v / ve) if ve > 0 else 1.0
    wet_mass = dry_mass * mass_ratio
    fuel_mass = wet_mass - dry_mass
    fuel_fraction = fuel_mass / wet_mass if wet_mass > 0 else 0.0

    return TsiolkovskyResult(
        mass_ratio=mass_ratio,
        fuel_fraction=fuel_fraction,
        wet_mass=wet_mass,
        fuel_mass=fuel_mass,
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_calculator.py -v
```

Expected: all PASS

- [ ] **Step 5: ruff + mypy**

```bash
ruff check kopdeltav/calculator.py && ruff format kopdeltav/calculator.py && mypy --strict kopdeltav/calculator.py
```

- [ ] **Step 6: Commit**

```bash
git add kopdeltav/calculator.py tests/test_calculator.py
git commit -m "feat(calculator): add launch_to_orbit, hohmann_transfer, tsiolkovsky"
```

---

### Task 10: calculator.py — Sanctar Reference Regression Tests

**Files:**
- Modify: `tests/test_calculator.py`
- Requires: Working parser + `sample_configs/Sanctar.cfg`

- [ ] **Step 1: Write Sanctar regression tests**

Append to `tests/test_calculator.py`:
```python
from pathlib import Path
from kopdeltav.parser import parse_config

SAMPLE_DIR = Path(__file__).parent.parent / "sample_configs"


class TestSanctarRegression:
    """Regression tests against Sanctar reference values from CLAUDE.md."""

    def _get_sanctar(self) -> CelestialBody:
        text = (SAMPLE_DIR / "Sanctar.cfg").read_text(encoding="utf-8")
        result = parse_config(text)
        return next(b for b in result.bodies if b.name == "Sanctar")

    def test_mu(self) -> None:
        sanctar = self._get_sanctar()
        assert math.isclose(sanctar.mu, 4.8424e12, rel_tol=1e-3)

    def test_escape_velocity(self) -> None:
        sanctar = self._get_sanctar()
        v_esc = escape_velocity(sanctar, 0.0)
        assert math.isclose(v_esc, 3802.0, rel_tol=0.01)

    def test_lko_velocity(self) -> None:
        sanctar = self._get_sanctar()
        v_circ = circular_velocity(sanctar, 80_000.0)
        assert math.isclose(v_circ, 2541.1, rel_tol=0.01)

    def test_sea_level_density(self) -> None:
        sanctar = self._get_sanctar()
        assert sanctar.atmosphere is not None
        rho = atmospheric_density(sanctar.atmosphere, 0.0)
        assert math.isclose(rho, 1.4096, rel_tol=0.02)

    def test_launch_rocket_dv(self) -> None:
        sanctar = self._get_sanctar()
        result = launch_to_orbit(sanctar, 80_000.0)
        assert math.isclose(result.total_rocket_dv, 3110.0, rel_tol=0.05)

    def test_launch_jet_dv(self) -> None:
        sanctar = self._get_sanctar()
        result = launch_to_orbit(sanctar, 80_000.0)
        assert math.isclose(result.total_jet_dv, 1982.0, rel_tol=0.05)
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_calculator.py::TestSanctarRegression -v
```

- [ ] **Step 3: Tune empirical constants if needed**

If reference values don't match within tolerance, adjust the gravity_loss / drag_loss / jet_saving coefficients in `launch_to_orbit`. Document changes.

- [ ] **Step 4: Commit**

```bash
git add tests/test_calculator.py
git commit -m "test(calculator): add Sanctar reference value regression tests"
```

---

### Task 11: i18n.py

**Files:**
- Create: `kopdeltav/i18n.py`

- [ ] **Step 1: Implement i18n.py**

```python
"""Internationalization for the kopdeltav CLI.

dict ベースの日本語/英語翻訳。
"""
from __future__ import annotations

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "ja": {
        "launch.title": "低軌道投入 ΔV",
        "launch.orbital_velocity": "軌道速度",
        "launch.surface_velocity": "地表自転速度",
        "launch.theoretical_dv": "理論 ΔV",
        "launch.gravity_loss": "重力損失（推定）",
        "launch.drag_loss": "大気抵抗損失（推定）",
        "launch.total_rocket": "ロケット合計 ΔV",
        "launch.jet_saving": "ジェット節約（推定）",
        "launch.total_jet": "ジェット併用 ΔV",
        "hohmann.title": "ホーマン遷移 ΔV",
        "hohmann.departure": "出発バーン",
        "hohmann.arrival": "到着バーン",
        "hohmann.total": "合計 ΔV",
        "hohmann.transfer_time": "遷移時間",
        "hohmann.ejection": "脱出バーン（低軌道から）",
        "tsiolkovsky.title": "ツィオルコフスキーの公式",
        "tsiolkovsky.mass_ratio": "質量比",
        "tsiolkovsky.fuel_fraction": "燃料比率",
        "tsiolkovsky.wet_mass": "湿重量",
        "tsiolkovsky.fuel_mass": "燃料質量",
        "body.radius": "半径",
        "body.gee_asl": "海面重力",
        "body.mu": "重力パラメータ",
        "body.soi": "影響圏",
        "body.atmosphere_depth": "大気圏高度",
        "body.escape_velocity": "脱出速度",
        "common.unit_ms": "m/s",
        "common.unit_m": "m",
        "common.unit_kg": "kg",
        "common.unit_s": "s",
        "error.gamedata_not_found": "GameDataディレクトリが見つかりません。パスを指定してください。",
        "error.no_kopernicus": "Kopernicusの設定ファイルが見つかりません。",
    },
    "en": {
        "launch.title": "Launch to Orbit ΔV",
        "launch.orbital_velocity": "Orbital velocity",
        "launch.surface_velocity": "Surface rotation speed",
        "launch.theoretical_dv": "Theoretical ΔV",
        "launch.gravity_loss": "Gravity loss (est.)",
        "launch.drag_loss": "Drag loss (est.)",
        "launch.total_rocket": "Total rocket ΔV",
        "launch.jet_saving": "Jet saving (est.)",
        "launch.total_jet": "Jet-assisted ΔV",
        "hohmann.title": "Hohmann Transfer ΔV",
        "hohmann.departure": "Departure burn",
        "hohmann.arrival": "Arrival burn",
        "hohmann.total": "Total ΔV",
        "hohmann.transfer_time": "Transfer time",
        "hohmann.ejection": "Ejection burn (from parking orbit)",
        "tsiolkovsky.title": "Tsiolkovsky Rocket Equation",
        "tsiolkovsky.mass_ratio": "Mass ratio",
        "tsiolkovsky.fuel_fraction": "Fuel fraction",
        "tsiolkovsky.wet_mass": "Wet mass",
        "tsiolkovsky.fuel_mass": "Fuel mass",
        "body.radius": "Radius",
        "body.gee_asl": "Surface gravity",
        "body.mu": "Gravitational parameter",
        "body.soi": "Sphere of influence",
        "body.atmosphere_depth": "Atmosphere depth",
        "body.escape_velocity": "Escape velocity",
        "common.unit_ms": "m/s",
        "common.unit_m": "m",
        "common.unit_kg": "kg",
        "common.unit_s": "s",
        "error.gamedata_not_found": "GameData directory not found. Please specify the path.",
        "error.no_kopernicus": "No Kopernicus config files found.",
    },
}


def t(key: str, lang: str = "ja") -> str:
    """Get translated string by dot-separated key.

    翻訳文字列を取得する。

    Args:
        key: Dot-separated key (e.g. "launch.title").
        lang: Language code ("ja" or "en").

    Returns:
        Translated string. Returns the key itself if not found.
    """
    strings = _TRANSLATIONS.get(lang, _TRANSLATIONS["ja"])
    return strings.get(key, key)
```

- [ ] **Step 2: Write tests for i18n**

`tests/test_i18n.py`:
```python
from __future__ import annotations

from kopdeltav.i18n import t


class TestI18n:
    def test_ja_key(self) -> None:
        assert t("launch.title", "ja") == "低軌道投入 ΔV"

    def test_en_key(self) -> None:
        assert t("launch.title", "en") == "Launch to Orbit ΔV"

    def test_unknown_key_returns_key(self) -> None:
        assert t("nonexistent.key", "ja") == "nonexistent.key"

    def test_default_lang_is_ja(self) -> None:
        assert t("launch.title") == "低軌道投入 ΔV"
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_i18n.py -v
```

Expected: all PASS

- [ ] **Step 4: ruff + mypy**

```bash
ruff check kopdeltav/i18n.py && ruff format kopdeltav/i18n.py && mypy --strict kopdeltav/i18n.py
```

- [ ] **Step 5: Commit**

```bash
git add kopdeltav/i18n.py tests/test_i18n.py
git commit -m "feat(i18n): add ja/en translation strings"
```

---

### Task 12: run.py — CLI

**Files:**
- Create: `run.py`

- [ ] **Step 1: Implement run.py**

```python
"""CLI entry point for KSPDeltaVForMods.

KSP1 惑星パック Mod 向け ΔV 計算 CLI。
Usage: python run.py [path]
"""
from __future__ import annotations

import sys
from pathlib import Path

from kopdeltav.calculator import (
    circular_velocity,
    escape_velocity,
    launch_to_orbit,
)
from kopdeltav.discovery import find_gamedata, scan_kopernicus_configs
from kopdeltav.i18n import t
from kopdeltav.models import CelestialBody
from kopdeltav.parser import parse_config, parse_gamedata


def _print_body_info(body: CelestialBody, indent: int = 0) -> None:
    """Print body info and launch ΔV recursively."""
    prefix = "  " * indent
    print(f"{prefix}{'─' * 2} {body.display_name} ({body.name})")
    print(f"{prefix}   {t('body.radius')}: {body.radius:,.0f} m")
    print(f"{prefix}   {t('body.gee_asl')}: {body.gee_asl:.3f} g")
    print(f"{prefix}   {t('body.mu')}: {body.mu:.4e} m³/s²")

    if body.soi != float("inf"):
        print(f"{prefix}   {t('body.soi')}: {body.soi:,.0f} m")

    v_esc = escape_velocity(body, 0.0)
    print(f"{prefix}   {t('body.escape_velocity')}: {v_esc:,.1f} m/s")

    if body.atmosphere is not None:
        depth = body.atmosphere.atmosphere_depth
        print(f"{prefix}   {t('body.atmosphere_depth')}: {depth:,.0f} m")
        result = launch_to_orbit(body, depth + 10_000.0)
        print(f"{prefix}   {t('launch.total_rocket')}: {result.total_rocket_dv:,.1f} m/s")
        print(f"{prefix}   {t('launch.total_jet')}: {result.total_jet_dv:,.1f} m/s")

    for child in body.children:
        _print_body_info(child, indent + 1)


def main() -> None:
    """Main CLI entry point."""
    user_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None

    # Single file mode
    if user_path is not None and user_path.is_file() and user_path.suffix == ".cfg":
        text = user_path.read_text(encoding="utf-8")
        result = parse_config(text)
        for w in result.warnings:
            print(f"⚠ {w}", file=sys.stderr)
        for body in result.bodies:
            if body.parent is None:
                _print_body_info(body)
        return

    # GameData mode
    try:
        gamedata = find_gamedata(user_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    configs = scan_kopernicus_configs(gamedata)
    if not configs:
        print(t("error.no_kopernicus"), file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(configs)} Kopernicus config(s) in {gamedata}")
    result = parse_gamedata(gamedata)
    for w in result.warnings:
        print(f"⚠ {w}", file=sys.stderr)

    for body in result.bodies:
        if body.parent is None:
            _print_body_info(body)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test manually**

```bash
python run.py sample_configs/Sanctar.cfg
```

Expected: prints Sanctar body info with ΔV calculations.

- [ ] **Step 3: ruff + mypy**

```bash
ruff check run.py && ruff format run.py && mypy run.py
```

- [ ] **Step 4: Commit**

```bash
git add run.py
git commit -m "feat(cli): add run.py CLI entry point"
```

---

### Task 13: Update __init__.py and CLAUDE.md

**Files:**
- Modify: `kopdeltav/__init__.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update package init with public API**

```python
"""KSPDeltaVForMods — Delta-V calculator for KSP1 planet pack mods."""
from __future__ import annotations

from kopdeltav.calculator import (
    LaunchResult,
    HohmannResult,
    TsiolkovskyResult,
    atmospheric_density,
    circular_velocity,
    escape_velocity,
    hohmann_transfer,
    launch_to_orbit,
    tsiolkovsky,
)
from kopdeltav.discovery import find_gamedata, scan_kopernicus_configs
from kopdeltav.models import (
    Atmosphere,
    CelestialBody,
    CurveKey,
    OrbitalElements,
    hermite_interp,
)
from kopdeltav.parser import ParseResult, parse_config, parse_gamedata
from kopdeltav.stock import get_stock_body, get_stock_system
from kopdeltav.i18n import t

__all__ = [
    "Atmosphere",
    "CelestialBody",
    "CurveKey",
    "HohmannResult",
    "LaunchResult",
    "OrbitalElements",
    "ParseResult",
    "TsiolkovskyResult",
    "atmospheric_density",
    "circular_velocity",
    "escape_velocity",
    "find_gamedata",
    "get_stock_body",
    "get_stock_system",
    "hermite_interp",
    "hohmann_transfer",
    "launch_to_orbit",
    "parse_config",
    "parse_gamedata",
    "scan_kopernicus_configs",
    "t",
    "tsiolkovsky",
]
```

- [ ] **Step 2: Update CLAUDE.md repository structure**

Add `stock.py`, `discovery.py`, and new test files to the repo structure section.

- [ ] **Step 3: Run full check suite**

```bash
ruff check kopdeltav/ run.py tests/ && ruff format --check kopdeltav/ run.py tests/ && mypy --strict kopdeltav/ && pytest tests/ -v
```

Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add kopdeltav/__init__.py CLAUDE.md
git commit -m "chore: update package exports and CLAUDE.md repo structure"
```

---

### Task 14: Final Integration Test and Format Pass

**Files:**
- All files

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=long
```

Expected: all pass

- [ ] **Step 2: Run full linting and formatting**

```bash
ruff format kopdeltav/ run.py tests/
ruff check kopdeltav/ run.py tests/
mypy --strict kopdeltav/
```

- [ ] **Step 3: Manual CLI test**

```bash
python run.py sample_configs/Sanctar.cfg
```

Verify output looks correct.

- [ ] **Step 4: Final commit if any format changes**

```bash
git status
# Stage only changed Python files (list specific files)
git add kopdeltav/ run.py tests/
git commit -m "style: format pass on all Python files"
```
