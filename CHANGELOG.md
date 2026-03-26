# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-03-26

### Added
- Subway-map style ΔV route display with ANSI colors and Unicode/ASCII fallback
- CLI internationalization (ja/en/id) with locale auto-detection and `--lang` flag
- Inner planet Hohmann transfer support (inward transfers)
- Sub-star-system routing with barycenter detection (Chaos, Grannus, etc.)
- Detail view option (`--detail`) for expanded route information
- Output format options (`--format text/md/json`)
- SegmentType enum for route step classification
- Terminal capability detection (color, Unicode, Windows ANSI)
- SIGPIPE handling for pipe safety
- README (en/ja/id), LICENSE (MIT), CHANGELOG
- CI workflow (GitHub Actions: ruff, mypy, pytest on Python 3.10/3.12)

### Fixed
- Inner planet destinations (Dasar, Valheilheim) no longer crash `compute_route`
- `sort_by_transfer_dv` simplified after inward Hohmann support

## [0.1.0] - 2026-03-26

### Added
- Kopernicus ConfigNode parser with modifier and comment handling
- ΔV calculation engine: launch to orbit, Hohmann transfer, escape velocity, Tsiolkovsky equation
- Interactive CLI mode with route navigation
- GameData directory scanner with JSON persistence
- Atmosphere modeling with cubic Hermite spline interpolation (KSP AnimationCurve compatible)
- Bilingual support infrastructure (ja/en)
