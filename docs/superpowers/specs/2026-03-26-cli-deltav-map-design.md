# CLI ΔV Map & Engine Improvements — Design Spec

**Date**: 2026-03-26
**Status**: Approved
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
| 5 | Detail view option | `run.py` |
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

**Impact**: `compute_route()` and `sort_by_transfer_dv()` can call `calculate_hohmann()` without
pre-swapping. Simplifies both callers.

### 1-B. Sub-Star-System Routing

**Problem**: Bodies like Chaos are barycenters of sub-star-systems. Current `compute_route()`
treats them as regular planets, making "land on Chaos" meaningless (R=10km barycenter).

**Detection**: A body is a "sub-star-system" when:
- It is a child of the parent star (Sun)
- It has children of its own
- The destination selected by the user is one of those children

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

- When destination is a barycenter (has children, tiny radius), **force sub-body selection**
  in the interactive UI — don't allow "land on Chaos" as a final destination.
- The `escape_dv_from_low_orbit(barycenter)` capture step uses the barycenter's μ, which
  is physically valid as a simplified model.
- Sub-moons of Farewell (Escape, Fin, etc.) are not navigable (2-level limit).

### 1-C. Inner Planet Route in `compute_route`

Apply the same inward-Hohmann support from 1-A to `compute_route()`. With `calculate_hohmann()`
now handling `r2 < r1` natively, no special casing is needed in the caller — just remove the
assumption that destination SMA > home SMA.

---

## 2. CLI Internationalization

### 2-A. Language Detection (`i18n.py`)

New function `detect_language() -> str`:

```
Priority:
1. --lang flag (passed explicitly)
2. LANG / LC_ALL environment variable (extract first 2 chars)
3. locale.getdefaultlocale() (works on Windows + Linux)
4. Fallback: "en"
```

Mapping: `ja*` → `"ja"`, `en*` → `"en"`, `id*` → `"id"`, unknown → `"en"`.

All in stdlib — no external dependencies.

### 2-B. `--lang` CLI Flag

Add `--lang {en,ja,id}` to `sys.argv` parsing (or migrate to `argparse`).
The flag overrides auto-detection. Passed as `lang` parameter throughout `run.py`.

### 2-C. Indonesian Language

Add `"id"` section to `_TRANSLATIONS` in `i18n.py`.
Update `SUPPORTED_LANGUAGES` to `("ja", "en", "id")`.

### 2-D. Replace Hardcoded Strings

All user-facing strings in `run.py` replaced with `get_text(key, lang)` calls.
`_body_brief`: `"R:"` → short form of `get_text("body.radius", lang)` (e.g., "R:", "半径:", "R:").

---

## 3. Subway-Map Style Route Display

### 3-A. Visual Format

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
- Graceful fallback: symbols only when terminal does not support color

### 3-B. Detail View

Toggled by `d` command after route display (or `--detail` flag).
Expands each segment with sub-items:

- **Launch**: orbital velocity, gravity loss, drag loss, jet savings
- **Escape**: surface escape velocity
- **Transfer**: transfer time, transfer orbit dimensions, phase angle
- **Destination info**: radius, gravity, atmosphere, SOI
- **Landing**: aerobrake savings if atmosphere present

Format uses `├`/`└` tree connectors under each segment.

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

### 4-B. CHANGELOG

```markdown
## [0.2.0] - 2026-03-xx
### Added
- Subway-map style ΔV route display with ANSI colors
- CLI internationalization (ja/en/id) with locale auto-detection
- Inner planet Hohmann transfer support
- Sub-star-system routing (Chaos, Grannus, etc.)
- Detail view option for ΔV routes
- README (en/ja/id), LICENSE, CHANGELOG

## [0.1.0] - 2026-03-26
### Added
- Kopernicus ConfigNode parser
- ΔV calculation engine (launch, Hohmann, escape, Tsiolkovsky)
- Interactive CLI mode with route navigation
- GameData scanner with JSON persistence
- Atmosphere modeling with cubic Hermite spline interpolation
```

### 4-C. CI Workflow

`.github/workflows/ci.yml`:

```yaml
on: [push, pull_request]
jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - ruff check kopdeltav/ api.py run.py tests/
      - ruff format --check kopdeltav/ api.py run.py tests/
      - mypy --strict kopdeltav/
      - pytest tests/ -v
```

CD (auto-release) is out of scope. Manual tag → GitHub Release for now.

### 4-D. Release Strategy

- Tag `v0.1.0` on current state (snapshot)
- GitHub Release with Python source (`kopdeltav/` + `run.py` + `requirements.txt`)
- Tag `v0.2.0` after this work completes
- PyPI deferred to `v1.0.0`

---

## 5. Branch & Issue Structure

All branches cut from `dev`.

| Issue | Branch | Content | Dependencies |
|-------|--------|---------|-------------|
| #1 | `dev/fix/inner-planet-hohmann` | 1-A, 1-B, 1-C | None |
| #2 | `dev/feature/cli-i18n` | 2-A, 2-B, 2-C, 2-D | #1 |
| #3 | `dev/feature/subway-map-display` | 3-A, 3-B | #2 |
| #4 | `dev/docs/readme-license-changelog` | 4-A, 4-B | None (parallel) |
| #5 | `dev/chore/ci-release` | 4-C, 4-D | None (parallel) |

**Execution order** (Approach A):
- Sequential: #1 → #2 → #3
- Parallel with above: #4 and #5 (independent, tmux + git worktree)

## 6. Parallel Work Strategy

Use TeamCreate with tmux for independent branches:

- **Group 1** (sequential): #1 → #2 → #3 (main agent)
- **Group 2** (parallel via worktree): #4 docs
- **Group 2** (parallel via worktree): #5 CI + release

Merge order: #4, #5 can merge to dev anytime. #1 → #2 → #3 merge sequentially.

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
- Overflow investigation for very distant planets (defer until reproducible)
