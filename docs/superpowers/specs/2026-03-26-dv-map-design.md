# ΔV Map Feature Design

Interactive ΔV map navigator for KSP1 planet pack mods.
Mother planet to destination, step-by-step cumulative ΔV with landing.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| cfg search | GameData/ recursive, exclude Kopernicus/ | Kopernicus is base mod, not planet content |
| Home world ID | `isHomeWorld = True` in Properties | Explicit config field, no name heuristics |
| Root (star) ID | Orbit node absent (primary), unresolved referenceBody (fallback) | Both checks for robustness |
| Sort order | Hohmann transfer ΔV ascending | Practical "easiest to reach" ordering |
| Landing ΔV | Show both powered & aerobrake cases | User needs both scenarios |
| CLI approach | Existing single-cfg mode preserved, new --scan and --interactive modes | Backwards compatible |
| Architecture | Core logic in kopdeltav/, CLI is thin wrapper | Reusable from API and frontend |

## 1. Model Changes

### models.py

Add two fields to `CelestialBody`:

```python
is_home_world: bool = False        # True if isHomeWorld = True in config
reference_body_name: str = ""      # Parent body name from Orbit/referenceBody
```

### parser.py

- Parse `isHomeWorld` from Properties node → `is_home_world`
- Parse `referenceBody` from Orbit node → `reference_body_name`

## 2. New Module: system.py

Manages a complete celestial system as a tree.

```python
@dataclass
class CelestialSystem:
    root: CelestialBody              # Star (root of tree)
    bodies: dict[str, CelestialBody] # name → body lookup
    home_world: CelestialBody        # isHomeWorld=True body

def scan_configs(gamedata_path: Path) -> CelestialSystem:
    """Recursively scan GameData/ for .cfg files, build tree.

    - Excludes Kopernicus/ directory
    - Copies found .cfg files to celestial_body/ directory
    - Builds parent/children tree from referenceBody
    - Identifies root: no Orbit node, or unresolved referenceBody
    - Identifies home world: isHomeWorld=True
    - Computes SOI for bodies where it's missing
    """

def build_tree(bodies: list[CelestialBody]) -> CelestialSystem:
    """Build parent/children tree from flat body list."""

def sort_by_transfer_dv(
    origin: CelestialBody,
    targets: list[CelestialBody],
) -> list[tuple[CelestialBody, float]]:
    """Sort targets by Hohmann transfer ΔV from origin (ascending)."""
```

### Tree construction logic

1. Index all bodies by name
2. For each body with `reference_body_name`:
   - Find parent in index → set `parent`, append to parent's `children`
3. Root = body with no Orbit node; fallback = body whose referenceBody is not in index
4. Home world = body with `is_home_world=True`
5. Planets = root's direct children
6. Moons = planet's children

### cfg search logic

1. Walk `gamedata_path` recursively
2. Skip directories named `Kopernicus` (case-insensitive)
3. Collect all `*.cfg` files
4. Parse each with `parse_bodies()`; some may yield 0 bodies (non-Kopernicus configs) — skip silently
5. Copy valid cfg files to `celestial_body/` directory
6. Build tree from all collected bodies

## 3. Calculator Extensions

### New functions

```python
def geostationary_altitude(body: CelestialBody) -> float:
    """r_geo = ∛(μT²/4π²), return r_geo - radius."""

def geostationary_dv(body: CelestialBody) -> HohmannResult:
    """Low orbit → geostationary Hohmann transfer."""

def escape_dv_from_low_orbit(body: CelestialBody) -> float:
    """ΔV to escape from low orbit. v_escape(LO alt) - v_circular(LO alt)."""

def landing_dv(body: CelestialBody) -> tuple[float, float | None]:
    """(powered_dv, aerobrake_dv).
    powered_dv ≈ orbital velocity at low orbit.
    aerobrake_dv = ~0 if atmosphere, None if no atmosphere.
    """

def interplanetary_dv(
    parent: CelestialBody,
    origin: CelestialBody,
    target: CelestialBody,
) -> float:
    """ΔV for origin LO → escape → Hohmann → target capture."""

def moon_transfer_dv(
    planet: CelestialBody,
    moon: CelestialBody,
) -> float:
    """ΔV from planet low orbit → moon orbit insertion."""
```

### DvStep and route computation

```python
@dataclass
class DvStep:
    label: str        # Step description
    dv: float         # ΔV for this step [m/s]
    cumulative: float # Cumulative ΔV from surface [m/s]
    note: str = ""    # e.g. "aerobrake possible"

def compute_route(
    system: CelestialSystem,
    destination: CelestialBody | None = None,
    moon: CelestialBody | None = None,
) -> list[DvStep]:
    """Compute full ΔV route from home world surface to destination.

    - destination=None → third cosmic velocity (star system escape)
    - destination=planet, moon=None → planet orbit + landing
    - destination=planet, moon=moon → moon orbit + landing

    Each step shows individual ΔV and cumulative total.
    Landing step shows both powered and aerobrake variants.
    """
```

### Route step breakdown

**To planet (no moon):**
1. Home world: launch to low orbit
2. Home world: escape to interplanetary
3. Hohmann transfer to planet
4. Planet: orbit insertion
5. Planet: landing (powered / aerobrake)

**To moon:**
1. Home world: launch to low orbit
2. Home world: escape to interplanetary
3. Hohmann transfer to planet
4. Planet: orbit insertion
5. Transfer to moon orbit
6. Moon: landing (powered / aerobrake)

**Third cosmic velocity (no destination):**
1. Home world: launch to low orbit
2. Home world: escape
3. Escape from star system

## 4. CLI Interactive Mode

### Invocation

```bash
# Existing: single cfg analysis (unchanged)
python run.py sample_configs/Sanctar.cfg

# New: scan GameData and start interactive
python run.py --scan /path/to/GameData

# New: use previously saved celestial_body/ data
python run.py --interactive
```

### Interactive flow

```
=== Star System ===
Home: Sanctar (670,000m, 1.1g)

[Home World]
  Low orbit:        3,110 m/s
  Geostationary:    X,XXX m/s
  Escape:           3,802 m/s

Select destination:
  1) Planet_A     (ΔV: 1,200 m/s)
  2) Planet_B     (ΔV: 2,500 m/s)
  [Enter] Third cosmic velocity

> 1

=== Sanctar → Planet_A ===
  Escape home:      XXX m/s
  Transfer:         1,200 m/s
  Orbit insertion:  XXX m/s
  Cumulative:       X,XXX m/s

  1) Moon_a (ΔV: 300 m/s)
  2) Moon_b (ΔV: 600 m/s)
  [Enter] Land on Planet_A

> [Enter]

=== Landing: Planet_A ===
  Powered landing:  XXX m/s
  Aerobrake:        ≈0 m/s (atmosphere)

  Total (powered):    X,XXX m/s
  Total (aerobrake):  X,XXX m/s
```

### celestial_body/ directory

- Created by `--scan` on first run
- Contains copies of parsed .cfg files
- Added to `.gitignore` (user-specific data)
- `--interactive` reads from here; prompts for GameData path if missing

## 5. API Extensions

### New endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/scan` | Scan GameData path, build system |
| GET | `/system` | Current CelestialSystem info (tree) |
| GET | `/system/home` | Home world + geostationary ΔV |
| GET | `/system/destinations` | Transfer destinations (ΔV sorted) |
| POST | `/calc/route` | Full ΔV route to destination |
| GET | `/bodies/{name}/moons` | Body's moons (ΔV sorted) |

### Request/Response models

```python
class ScanRequest(BaseModel):
    gamedata_path: str
    exclude_dirs: list[str] = ["Kopernicus"]

class SystemResponse(BaseModel):
    root: BodySummary
    home_world: BodyDetail
    body_count: int
    tree: list[BodyTreeNode]

class BodyTreeNode(BaseModel):
    name: str
    display_name: str
    children: list[BodyTreeNode]

class DestinationEntry(BaseModel):
    body: BodySummary
    transfer_dv: float

class RouteRequest(BaseModel):
    destination: str | None = None
    moon: str | None = None

class RouteResponse(BaseModel):
    steps: list[DvStepResponse]
    total_powered: float
    total_aerobrake: float | None

class DvStepResponse(BaseModel):
    label: str
    dv: float
    cumulative: float
    note: str = ""
```

### Error handling

| Condition | Status | Message |
|-----------|--------|---------|
| GameData path not found | 404 | Path does not exist |
| No .cfg files found | 404 | No config files found |
| No home world | 422 | No body with isHomeWorld=True |
| Unknown body name | 404 | Body not found |
| Invalid destination/moon combo | 422 | Moon is not a child of destination |

## 6. Testing Strategy

### Unit tests
- `test_system.py`: tree construction, cfg scanning (mock filesystem), sort by ΔV
- `test_calculator.py`: new functions (geostationary, landing, interplanetary, route)

### Integration tests
- Parse Sanctar.cfg → build single-body system → compute routes
- Full scan of sample_configs/ → verify tree structure

### Regression
- All existing reference values must still pass
- Geostationary altitude for Sanctar (derivable from rotationalPeriod and μ)
