# CLI ΔV Map & Engine Improvements — Design Spec

**Date**: 2026-03-26
**Status**: Approved (rev.2 — incorporates user review feedback)
**Approach**: A (Core logic first)

## Overview

Enhance the KSPDeltaVForMods CLI with subway-map-style ΔV route display,
multilingual support, calculation engine fixes, and project scaffolding
(README, LICENSE, CHANGELOG, CI, Release).

## Scope

| # | Feature | Layer |
|---|---------|-------|
| 1 | Inner planet Hohmann transfer fix | `calculator.py` |
| 2 | Sub-star-system routing (2-level) | `calculator.py`, `run.py` |
| 3 | CLI i18n (ja/en/id) + locale detection | `i18n.py`, `run.py` |
| 4 | Subway-map style route display | `run.py` |
| 5 | Detail view option + output formats | `run.py` |
| 6 | README (en/ja/id), LICENSE, CHANGELOG | root |
| 7 | CI workflow + v0.1.0 release | `.github/workflows/`, tags |

Frontend graphical ΔV map is **out of scope** (separate phase).

---

## 1. Calculation Engine Fixes

### 1-A. Inner Planet Hohmann Transfer

**Problem**: `calculate_hohmann()` raises `ValueError` when `target_sma < parking_orbit_radius`.
`sort_by_transfer_dv()` already handles this by swapping min/max, but `compute_route()` does not.

**Solution**: Modify `calculate_hohmann()` to handle inward transfers:

- When `r2 < r1`, swap `r1`/`r2` internally for vis-viva computation
- Swap `departure_dv` and `arrival_dv` in the result
- Add `inward: bool` field to `HohmannResult` for display layer to distinguish direction
- Remove the `r2 <= r1` ValueError; only reject `r1 == r2` (zero-cost transfer)

**Type safety**: Make `HohmannResult` a `@dataclass(frozen=True)` to prevent accidental mutation
after construction.

**Impact**: `compute_route()` and `sort_by_transfer_dv()` can call `calculate_hohmann()` without
pre-swapping. Simplifies both callers.

**Required tests**:
- `r2 < r1`: verify `inward=True`, departure/arrival ΔV swapped correctly
- `r1 == r2`: verify `ValueError`
- Known textbook Hohmann case: verify ±1e-6 relative error
- Existing Sanctar reference values: no regression

### 1-B. Sub-Star-System Routing

**Problem**: Bodies like Chaos are barycenters of sub-star-systems. Current `compute_route()`
treats them as regular planets, making "land on Chaos" meaningless (R=10km barycenter).

**Barycenter detection heuristic** (no `is_barycenter` field in data):
A body is treated as a barycenter when ALL of:
- It is a child of the parent star (Sun)
- It has children of its own
- Its radius is unusually small relative to its children (radius < min(child.radius))

This heuristic correctly identifies Chaos (R=10km, children have R >> 10km) without
false-positiving on normal planets with moons (e.g., Magnifica where R >> moon R).

**Route structure** (e.g., Kerbin → Farewell in Chaos system):

```
1. Launch to low orbit (Kerbin)
2. Escape Kerbin
3. Interplanetary transfer (Sun frame: Kerbin orbit → Chaos orbit)
4. Enter Chaos system (excess velocity → capture)
5. Intra-system transfer (Chaos frame: entry orbit → Farewell orbit)
6. Land on Farewell
```

**Implementation**: The existing `compute_route(destination=Chaos, moon=Farewell)` path
already computes a two-hop route (Sun-frame Hohmann → capture → intra-system Hohmann → land).
This works physically because Chaos has its own μ and SOI. Changes needed:

- When destination is a barycenter (detected by heuristic), **force sub-body selection**
  in the interactive UI — don't allow "land on barycenter" as a final destination.
- The `escape_dv_from_low_orbit(barycenter)` capture step uses the barycenter's μ, which
  is physically valid as a simplified model.
- Sub-moons of Farewell (Escape, Fin, etc.) are not navigable (2-level limit).

**Required tests**:
- Kerbin → Chaos → Farewell: 2-hop route with correct segment count
- Barycenter detection: Chaos=true, Magnifica=false, Kerbin=false
- UI: barycenter selected without sub-body → forced selection prompt

### 1-C. Inner Planet Route in `compute_route`

Apply the same inward-Hohmann support from 1-A to `compute_route()`. With `calculate_hohmann()`
now handling `r2 < r1` natively, no special casing is needed in the caller — just remove the
assumption that destination SMA > home SMA.

### 1-D. Type Safety Improvements

- `HohmannResult`: `@dataclass(frozen=True)`
- `DvStep`: `@dataclass(frozen=True)`
- `LaunchResult`: `@dataclass(frozen=True)`
- Add `SegmentType` enum: `LAUNCH`, `ESCAPE`, `TRANSFER`, `CAPTURE`, `LANDING`,
  `SYSTEM_ESCAPE`, `MOON_TRANSFER`, `MOON_LANDING`
- Attach `SegmentType` to each `DvStep` for display layer to determine color/symbol
- Route total ΔV: `sum(seg.dv for seg in segments)` with NaN safety guard

---

## 2. CLI Internationalization

### 2-A. Language Detection (`i18n.py`)

New function `detect_language(override: str | None = None) -> str`:

```
Priority:
1. override parameter (from --lang flag)
2. LC_MESSAGES environment variable (Linux standard)
3. LANG environment variable
4. LC_ALL environment variable
5. locale.getlocale() (cross-platform, preferred over deprecated getdefaultlocale)
6. Fallback: "en"
```

Mapping: `ja*` → `"ja"`, `en*` → `"en"`, `id*` → `"id"`, unknown → `"en"`.

All in stdlib — no external dependencies. `locale.getdefaultlocale()` is avoided
(deprecated since Python 3.11, removed in 3.15).

### 2-B. `--lang` CLI Flag

Add `--lang {en,ja,id}` to `sys.argv` parsing (or migrate to `argparse`).
The flag overrides auto-detection. Passed as `lang` parameter throughout `run.py`.

### 2-C. Indonesian Language

Add `"id"` section to `_TRANSLATIONS` in `i18n.py`.
Update `SUPPORTED_LANGUAGES` to `("ja", "en", "id")`.

### 2-D. Replace Hardcoded Strings

All user-facing strings in `run.py` replaced with `get_text(key, lang)` calls.
`_body_brief`: `"R:"` → short form of `get_text("body.radius_short", lang)`
(ja: "半径:", en: "R:", id: "R:").

### 2-E. Key Safety

`get_text()` behavior for undefined keys:
- Return English translation if key exists in `"en"` but not in requested language
- Return the key string itself as last resort
- Log a warning (`logger.warning`) on first occurrence of each missing key
- Never raise an exception for a missing translation

**Required tests**:
- All keys in `ja` and `id` exist in `en` (completeness check)
- Undefined key returns English fallback
- `--lang` overrides `LANG` env var
- No args + no env → auto-detect → `"en"` default

---

## 3. Subway-Map Style Route Display

### 3-A. Terminal Capability Detection

Auto-detect terminal features at startup:

- **Color**: `sys.stdout.isatty()` AND `NO_COLOR` env not set AND
  `TERM != "dumb"`. Check `COLORTERM` for 256/truecolor.
- **Unicode**: stdout encoding is UTF-8. If not, fall back to ASCII symbols.
- **Windows ANSI**: Call `enable_ansi_on_windows()` at startup using
  `ctypes.windll.kernel32.SetConsoleMode()` — no external deps. If it fails,
  fall back to no-color mode.

ASCII fallback symbols: `(*)` for `●`, `(o)` for `○`, `^` for `▲`, `v` for `▼`,
`|` for `│`, `+--` for `├`, `\--` for `└`.

### 3-B. Visual Format

```
── ΔV Route: Kerbin → Magnifica ──────────────────

  ● Kerbin (surface)
  │  ▲ 3,108 m/s   Launch to low orbit
  ●─ Low orbit (80 km)
  │  ▲ 1,053 m/s   Escape Kerbin
  ○─ Kerbin SOI edge
  │  ▲   459 m/s   Interplanetary transfer
  ○─ Magnifica SOI edge
  │  ▼   298 m/s   Capture
  ●─ Low orbit (50 km)
  │  ▼   719 m/s   Landing
  ● Magnifica (surface)

  Total: 5,636 m/s
```

- `●` solid node = physical location (surface, stable orbit)
- `○` hollow node = transient point (SOI boundary)
- `▲` acceleration burn, `▼` deceleration burn
- ANSI color per segment type: launch=green, escape=yellow, transfer=blue,
  capture=cyan, landing=red
- Graceful fallback per 3-A rules

### 3-C. Detail View

Toggled by `d` command after route display (or `--detail` flag).
Expands each segment with sub-items:

- **Launch**: orbital velocity, gravity loss, drag loss, jet savings
- **Escape**: surface escape velocity
- **Transfer**: transfer time (d/h/m format, i18n-aware), transfer orbit dimensions
  (periapsis × apoapsis in Mm), phase angle (degrees, 1 decimal)
- **Destination info**: radius, gravity, atmosphere, SOI
- **Landing**: aerobrake savings if atmosphere present

Number formatting follows locale: ja/id use `,` for thousands, `.` for decimal.
Units are always SI (m/s, m, s, kg) — no locale-specific unit conversion.

Format uses `├`/`└` tree connectors under each segment.

### 3-D. Output Formats (`--format`)

`--format {text,md,json}` (default: `text`)

- **text**: Subway-map display with ANSI colors (current default)
- **md**: Markdown table format (no ANSI, pipe-safe)
- **json**: Machine-readable route data for tool integration

JSON schema:
```json
{
  "route": {
    "from": "Kerbin",
    "to": "Magnifica",
    "total_dv": 5636.0,
    "segments": [
      {
        "type": "launch",
        "label": "Launch to low orbit",
        "dv": 3108.0,
        "cumulative": 3108.0,
        "from": "Kerbin (surface)",
        "to": "Low orbit (80 km)",
        "details": {
          "orbital_velocity": 2541.1,
          "gravity_loss": 382.0,
          "drag_loss": 185.0,
          "jet_savings": 128.0
        }
      }
    ]
  }
}
```

**Required tests**:
- ANSI on/off: `TERM=dumb` / `NO_COLOR=1` / non-TTY (`> out.txt`) → no color codes
- Unicode: `PYTHONIOENCODING=ascii` → ASCII symbol fallback
- `--format json | python -m json.tool` passes (CI validation)
- `--format md` produces valid markdown table
- Snapshot tests: known route → expected output (text/md/json)

### 3-E. SIGPIPE / BrokenPipe Handling

When output is piped (e.g., `python run.py ... | head -n1`), handle `BrokenPipeError`
gracefully: suppress the traceback, exit with code 0. Standard Python pattern:

```python
import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
```

---

## 4. Project Scaffolding

### 4-A. Files

| File | Content |
|------|---------|
| `README.md` | English (main). Links to ja/id versions. |
| `README-ja.md` | Japanese |
| `README-id.md` | Indonesian |
| `LICENSE` | MIT (full text) |
| `CHANGELOG.md` | Keep a Changelog format |

README follows the user's template from CLAUDE.md (global).

### 4-B. README Additional Sections

Beyond the standard template, include:

- **Output sample**: Full `--detail --format text` example for a known route
  (e.g., Kerbin → Magnifica)
- **i18n**: Language detection priority, supported languages, `--lang` usage
- **Windows notes**: ANSI color support (Win10+ native, older → symbols only)
- **JSON schema**: Brief description of `--format json` output structure
  with link to full schema in docs
- **KSP2 non-support**: Explicitly state this tool targets KSP1 + Kopernicus only.
  KSP2 is not supported and there are no plans to support it.

### 4-C. CHANGELOG

```markdown
## [0.2.0] - 2026-03-xx
### Added
- Subway-map style ΔV route display with ANSI colors
- CLI internationalization (ja/en/id) with locale auto-detection
- Inner planet Hohmann transfer support
- Sub-star-system routing (Chaos, Grannus, etc.)
- Detail view option for ΔV routes
- Output format options (text/md/json)
- README (en/ja/id), LICENSE, CHANGELOG
- CI workflow

## [0.1.0] - 2026-03-26
### Added
- Kopernicus ConfigNode parser
- ΔV calculation engine (launch, Hohmann, escape, Tsiolkovsky)
- Interactive CLI mode with route navigation
- GameData scanner with JSON persistence
- Atmosphere modeling with cubic Hermite spline interpolation
```

### 4-D. CI Workflow

`.github/workflows/ci.yml`:

```yaml
name: CI
on: [push, pull_request]

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
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - run: ruff check kopdeltav/ api.py run.py tests/
      - run: ruff format --check kopdeltav/ api.py run.py tests/
      - run: mypy --strict kopdeltav/
      - run: pytest tests/ -v
```

Two Python versions (3.10 minimum, 3.12 current) on ubuntu-latest.
Multi-OS (Windows/macOS) deferred until needed.
CD (auto-release) is out of scope. Manual tag → GitHub Release for now.

### 4-E. Release Strategy

- Tag `v0.1.0` on current state (snapshot)
- GitHub Release with Python source (`kopdeltav/` + `run.py` + `requirements.txt`)
- Tag `v0.2.0` after this work completes
- PyPI deferred to `v1.0.0`

---

## 5. Branch & Issue Structure

All branches cut from `dev`.

| Issue | Branch | Content | Dependencies |
|-------|--------|---------|-------------|
| #1 | `dev/fix/inner-planet-hohmann` | 1-A, 1-B, 1-C, 1-D | None |
| #2 | `dev/feature/cli-i18n` | 2-A, 2-B, 2-C, 2-D, 2-E | #1 |
| #3 | `dev/feature/subway-map-display` | 3-A~3-E | #2 |
| #4 | `dev/docs/readme-license-changelog` | 4-A, 4-B, 4-C | None (parallel) |
| #5 | `dev/chore/ci-release` | 4-D, 4-E | None (parallel) |

**Execution order** (Approach A):
- Sequential: #1 → #2 → #3
- Parallel with above: #4 and #5 (independent, tmux + git worktree)

## 6. Parallel Work Strategy

Use TeamCreate with tmux for independent branches:

- **Group 1** (sequential): #1 → #2 → #3 (main agent)
- **Group 2** (parallel via worktree): #4 docs
- **Group 3** (parallel via worktree): #5 CI + release

Merge order: #4, #5 can merge to dev anytime. #1 → #2 → #3 merge sequentially.

---

## 7. Test Checklist

### Calculation

- [ ] `r2 < r1`: `inward=True`, departure/arrival ΔV swapped correctly
- [ ] `r1 == r2`: `ValueError` raised
- [ ] Known textbook Hohmann case matches ±1e-6 relative error
- [ ] Sanctar reference values: no regression
- [ ] Kerbin → Chaos → Farewell: 2-hop route, correct segment count and types
- [ ] Barycenter detection: Chaos=true, Magnifica=false, Kerbin=false
- [ ] `DvStep`, `HohmannResult` are frozen (mutation raises `FrozenInstanceError`)

### Display / i18n

- [ ] ANSI disabled: `TERM=dumb` / `NO_COLOR=1` / non-TTY → no escape codes in output
- [ ] Unicode disabled: `PYTHONIOENCODING=ascii` → ASCII symbol fallback
- [ ] ja/en/id: all translation keys present (automated completeness check)
- [ ] Undefined key → English fallback + warning logged
- [ ] `--detail`: phase angle, transfer time, orbit dimensions in correct units
- [ ] Number format: thousands separator, decimal places consistent per locale

### CLI

- [ ] `--lang ja` overrides `LANG=en_US.UTF-8`
- [ ] No args + no env → auto-detect → `"en"` default
- [ ] Barycenter destination without sub-body → forced selection prompt
- [ ] `--format json | python -m json.tool` succeeds
- [ ] `--format md` produces parseable markdown
- [ ] Snapshot tests: known route → expected output for text/md/json
- [ ] SIGPIPE: `python run.py ... | head -n1` exits silently (no traceback)
- [ ] Windows: `enable_ansi_on_windows()` called, fallback if unavailable

### CI

- [ ] Python 3.10 and 3.12 both pass
- [ ] ruff check + format, mypy --strict, pytest all green

---

## Commit Message Convention

All commits in **English** (public repository).
Format: `<type>(scope): title` per Conventional Commits.
No `Co-Authored-By` line.

## Out of Scope

- Frontend graphical ΔV map (separate phase)
- KSP2 support
- PyPI publishing
- CD automation
- Multi-OS CI (Windows/macOS)
- `--seed` for future stochastic search (noted for later)
- Overflow investigation for very distant planets (defer until reproducible)
