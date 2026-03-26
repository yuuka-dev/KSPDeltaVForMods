[日本語](README-ja.md) | [Bahasa Indonesia](README-id.md)

# KSPDeltaVForMods

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

> Delta-V calculator for KSP1 planet pack mods powered by Kopernicus

## Overview

KSPDeltaVForMods parses Kopernicus `.cfg` files and computes orbital mechanics delta-v values including launch-to-orbit, Hohmann transfers, escape burns, and mass ratios with full atmosphere modeling.

### Why?

Delta-v maps exist for stock KSP, but not for modded planet packs. If you install a planet pack like Celestial Harmony, you have no reference for how much delta-v you need to reach orbit or transfer between planets. This tool reads the mod's Kopernicus config files and calculates everything automatically.

## Key Features

- **Kopernicus ConfigNode Parser** -- Handles modifiers, comments, nested nodes, and AnimationCurve keys
- **Delta-V Calculation Engine** -- Launch to orbit, Hohmann transfer, escape velocity, Tsiolkovsky rocket equation
- **Atmosphere Modeling** -- Cubic Hermite spline interpolation compatible with KSP's AnimationCurve
- **Interactive CLI** -- Navigate the celestial body tree and compute routes between bodies
- **GameData Scanner** -- Recursively scans a KSP GameData directory and persists parsed data as JSON

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Core Library | Python 3.10+ | Zero external dependencies |
| CLI | Python standalone | `python run.py` -- no pip install required |
| Backend API | FastAPI + Uvicorn | Planned |
| Frontend | Vue 3 + Vite + TypeScript | Planned |
| Desktop | Tauri v2 (Rust) | Planned |

## Getting Started

### Prerequisites

- Python 3.10 or later

### Usage

```bash
git clone https://github.com/yuuka-dev/KSPDeltaVForMods.git
cd KSPDeltaVForMods
python run.py --scan /path/to/KSP/GameData
python run.py --interactive
```

You can also calculate delta-v for a single config file:

```bash
python run.py sample_configs/Sanctar.cfg
```

## KSP2 Note

This tool targets KSP1 + Kopernicus only. KSP2 is not supported and there are no plans to support it.

## License

[MIT](LICENSE)
