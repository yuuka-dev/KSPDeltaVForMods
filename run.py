"""Standalone CLI for KSP ΔV calculations from Kopernicus config files.

Kopernicus .cfg ファイルからΔV計算結果を表示するスタンドアロンCLI。
pip 不要。python run.py path/to/config.cfg で実行可能。

Usage:
    python run.py <config.cfg>           Single file analysis (existing mode)
    python run.py --scan <GameData_path> Scan GameData and start interactive mode
    python run.py --interactive          Load from celestial_body/ and start interactive
    python run.py --lang en <config.cfg> Specify language (ja/en/id)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from kopdeltav.calculator import (
    DvStep,
    LaunchResult,
    calculate_launch,
    compute_route,
    escape_dv_from_low_orbit,
    escape_velocity,
    geostationary_altitude,
    geostationary_dv,
    low_orbit_altitude,
    surface_density,
)
from kopdeltav.i18n import SUPPORTED_LANGUAGES, detect_language, get_text
from kopdeltav.models import CelestialBody
from kopdeltav.parser import parse_bodies
from kopdeltav.system import (
    CelestialSystem,
    is_barycenter,
    load_system,
    scan_configs,
    sort_by_transfer_dv,
)

# Suppress noisy debug/info/warning logs from kopdeltav modules in CLI.
logging.basicConfig(level=logging.ERROR)

CELESTIAL_BODY_DIR = Path("celestial_body")


def _fmt_number(value: float, decimals: int = 0) -> str:
    """Format a number with thousand separators.

    数値を桁区切り付きでフォーマットする。

    Args:
        value: The number to format.
        decimals: Number of decimal places.

    Returns:
        Formatted string with comma separators.
    """
    if decimals > 0:
        return f"{value:,.{decimals}f}"
    return f"{value:,.0f}"


def _print_body(body: CelestialBody, lang: str) -> None:
    """Print formatted ΔV information for a single celestial body.

    天体のΔV情報を整形して出力する。

    Args:
        body: The celestial body to display.
        lang: Language code for display strings.
    """
    # Header
    display = body.display_name if body.display_name != body.name else body.name
    if display != body.name:
        print(f"\n=== {body.name} ({display}) ===")
    else:
        print(f"\n=== {body.name} ===")

    # Basic properties
    v_esc = escape_velocity(body, 0.0)
    print(f"  {get_text('body.radius_short', lang)}:           {_fmt_number(body.radius)} m")
    print(f"  {get_text('body.gravity', lang)}:       {body.gee_asl:.2f} g")
    print(f"  \u03bc:              {body.mu:.4e} m\u00b3/s\u00b2")
    print(
        f"  {get_text('route.escape', lang)}:       {_fmt_number(v_esc, 1)}"
        f" {get_text('common.unit_ms', lang)}"
    )

    # Atmosphere
    if body.atmosphere is not None:
        atmo = body.atmosphere
        rho = surface_density(body)
        print()
        print(f"  [{get_text('atmosphere.title', lang)}]")
        print(
            f"  {get_text('atmosphere.depth', lang)}:   {_fmt_number(atmo.atmosphere_depth)}"
            f" {get_text('common.unit_m', lang)}"
        )
        print(
            f"  {get_text('atmosphere.sea_level_pressure', lang)}:       "
            f"{atmo.pressure_at_sea_level:.1f} {get_text('common.unit_kpa', lang)}"
        )
        print(
            f"  {get_text('atmosphere.sea_level_temperature', lang)}:       "
            f"{atmo.temperature_at_sea_level:.1f} {get_text('common.unit_k', lang)}"
        )
        if rho is not None:
            print(
                f"  {get_text('atmosphere.sea_level_density', lang)}:       "
                f"{rho:.3f} {get_text('common.unit_kgm3', lang)}"
            )

    # Orbit
    if body.orbit is not None:
        orb = body.orbit
        print()
        print(f"  [{get_text('hohmann.title', lang)}]")
        print(f"  SMA:     {_fmt_number(orb.semi_major_axis)} {get_text('common.unit_m', lang)}")
        print(f"  e:         {orb.eccentricity:.5f}")
        print(f"  i:     {orb.inclination:.2f}\u00b0")

    # Launch ΔV
    alt = low_orbit_altitude(body)
    result: LaunchResult = calculate_launch(body, alt)
    print()
    print(
        f"  [{get_text('launch.title', lang)}]"
        f" ({get_text('launch.target_altitude', lang)}: {_fmt_number(alt)}"
        f" {get_text('common.unit_m', lang)})"
    )
    print(
        f"  {get_text('launch.orbital_velocity', lang)}:       "
        f"{_fmt_number(result.orbital_velocity, 1)} {get_text('common.unit_ms', lang)}"
    )
    print(
        f"  {get_text('launch.gravity_loss', lang)}:       "
        f"{_fmt_number(result.gravity_loss, 1)} {get_text('common.unit_ms', lang)}"
    )
    print(
        f"  {get_text('launch.drag_loss', lang)}:   "
        f"{_fmt_number(result.drag_loss, 1)} {get_text('common.unit_ms', lang)}"
    )
    print(
        f"  {get_text('launch.total_rocket', lang)}:     "
        f"~{_fmt_number(result.total_rocket, 0)} {get_text('common.unit_ms', lang)}"
    )
    if result.jet_savings > 0:
        print(
            f"  {get_text('launch.total_with_jets', lang)}: "
            f"~{_fmt_number(result.total_with_jets, 0)} {get_text('common.unit_ms', lang)}"
        )

    print()


def _print_home_info(system: CelestialSystem, lang: str) -> None:
    """Print home world summary with geostationary and escape info.

    ホームワールドの概要(静止軌道・脱出速度含む)を表示する。

    Args:
        system: The celestial system containing the home world.
        lang: Language code for display strings.
    """
    home = system.home_world
    alt = low_orbit_altitude(home)
    result = calculate_launch(home, alt)

    print(f"\n=== {get_text('system.star', lang)} ===")
    radius_str = _fmt_number(home.radius)
    print(
        f"{get_text('system.home_world', lang)}: {home.display_name}"
        f" ({get_text('body.radius_short', lang)}: {radius_str}"
        f" {get_text('common.unit_m', lang)},"
        f" {get_text('body.gravity', lang)}: {home.gee_asl:.1f}g)"
    )
    print()

    # Low orbit
    rocket_str = (
        f"~{_fmt_number(result.total_rocket, 0)}"
        f" {get_text('common.unit_ms', lang)}"
        f" ({get_text('launch.total_rocket', lang)})"
    )
    if result.jet_savings > 0:
        jet_str = (
            f" / ~{_fmt_number(result.total_with_jets, 0)}"
            f" {get_text('common.unit_ms', lang)}"
            f" ({get_text('launch.total_with_jets', lang)})"
        )
    else:
        jet_str = ""
    print(f"[{get_text('launch.title', lang)}]  {rocket_str}{jet_str}")

    # Geostationary
    try:
        geo_alt = geostationary_altitude(home)
        geo = geostationary_dv(home)
        print(
            f"[{get_text('launch.geostationary', lang)}]"
            f" ({get_text('launch.target_altitude', lang)}: {_fmt_number(geo_alt)}"
            f" {get_text('common.unit_m', lang)})"
            f"  \u0394V: {_fmt_number(geo.total_dv, 0)} {get_text('common.unit_ms', lang)}"
        )
    except ValueError:
        print(f"[{get_text('launch.geostationary', lang)}] {get_text('common.error', lang)}")

    # Escape from low orbit
    esc_dv = escape_dv_from_low_orbit(home)
    print(
        f"[{get_text('route.escape', lang)}]"
        f"    \u0394V: {_fmt_number(esc_dv, 0)} {get_text('common.unit_ms', lang)}"
    )


def _print_route(steps: list[DvStep], lang: str) -> None:
    """Print ΔV route with cumulative totals.

    ΔVルートを累積値とともに表示する。

    Args:
        steps: Ordered list of DvStep objects representing each maneuver.
        lang: Language code for display strings.
    """
    print()
    print(f"--- \u0394V{get_text('route.total', lang)} ---")
    for i, step in enumerate(steps, 1):
        note_str = f"  ({step.note})" if step.note else ""
        print(
            f"  {i:2d}. {step.label:<35}"
            f"  {_fmt_number(step.dv, 0):>8} {get_text('common.unit_ms', lang)}"
            f"  [{get_text('route.cumulative', lang)}:"
            f" {_fmt_number(step.cumulative, 0)} {get_text('common.unit_ms', lang)}]"
            f"{note_str}"
        )
    if steps:
        print(
            f"\n  {get_text('route.total', lang)}\u0394V:"
            f" {_fmt_number(steps[-1].cumulative, 0)} {get_text('common.unit_ms', lang)}"
        )


def _print_dest_list(
    ranked: list[tuple[CelestialBody, float]],
    parent: CelestialBody | None,
    lang: str,
) -> None:
    """Print the destination selection list.

    目的地選択リストを表示する。

    Args:
        ranked: List of (body, dv) tuples sorted by transfer ΔV.
        parent: The parent body of the home world.
        lang: Language code for display strings.
    """
    print(f"{get_text('system.select_destination', lang)}:")
    for i, (body, dv) in enumerate(ranked, 1):
        is_moon = body.parent is not None and body.parent is not parent
        marker = f" [{get_text('system.moons', lang)}]" if is_moon else ""
        print(
            f"  {i}) {body.display_name:<30}{marker}"
            f"  (\u0394V: {_fmt_number(dv, 0)} {get_text('common.unit_ms', lang)})"
        )
    third = get_text("route.third_cosmic", lang)
    sys_esc = get_text("route.system_escape", lang)
    print(f"  [Enter] {third}({sys_esc})")
    print(f"  q) {get_text('common.reset', lang)}")


def _interactive_mode(system: CelestialSystem, lang: str) -> None:
    """Interactive ΔV map navigator using input().

    input() を使ったインタラクティブΔVマップナビゲーター。

    Args:
        system: The celestial system to navigate.
        lang: Language code for display strings.
    """
    home = system.home_world
    parent = home.parent

    _print_home_info(system, lang)

    # Build list of sibling planets (bodies orbiting same parent as home)
    if parent is not None:
        siblings = [b for b in parent.children if b is not home]
        ranked = sort_by_transfer_dv(home, siblings)
    else:
        ranked = []

    print()
    _print_dest_list(ranked, parent, lang)

    while True:
        try:
            raw = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if raw.lower() in ("q", "quit", "exit"):
            break

        if raw == "":
            # Third cosmic velocity
            try:
                steps = compute_route(system, destination=None)
                _print_route(steps, lang)
            except ValueError as exc:
                print(f"{get_text('common.error', lang)}: {exc}", file=sys.stderr)
            continue

        # Numeric selection
        try:
            idx = int(raw) - 1
        except ValueError:
            print(f"  {get_text('system.select_destination', lang)}")
            continue

        if idx < 0 or idx >= len(ranked):
            print(f"  1\u301c{len(ranked)}")
            continue

        dest_body, _ = ranked[idx]

        # Ask for moon / sub-body selection if destination has children
        moons = dest_body.children
        moon: CelestialBody | None = None

        if moons and is_barycenter(dest_body):
            # Barycenter: must select a sub-body (cannot land on barycenter).
            print(f"\n{dest_body.name} {get_text('system.select_moon', lang)}:")
            for j, m in enumerate(moons, 1):
                m_display = m.display_name if m.display_name != m.name else m.name
                m_label = f"{m.name} ({m_display})" if m_display != m.name else m.name
                print(f"  {j}) {m_label}")

            while True:
                try:
                    moon_raw = input(f"{get_text('system.select_moon', lang)} > ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break

                if moon_raw == "":
                    print(f"  {get_text('system.select_moon', lang)}")
                    continue

                try:
                    moon_idx = int(moon_raw) - 1
                    if 0 <= moon_idx < len(moons):
                        moon = moons[moon_idx]
                        break
                    else:
                        print(f"  1\u301c{len(moons)}")
                        continue
                except ValueError:
                    print(f"  1\u301c{len(moons)}")
                    continue
            else:
                # while loop ended via break from EOFError/KeyboardInterrupt
                break

        elif moons:
            # Normal body with children (moons): offer optional moon selection.
            print(f"\n{dest_body.name} {get_text('system.moons', lang)}:")
            for j, m in enumerate(moons, 1):
                m_display = m.display_name if m.display_name != m.name else m.name
                m_label = f"{m.name} ({m_display})" if m_display != m.name else m.name
                print(f"  {j}) {m_label}")
            print(f"  [{get_text('system.press_enter_land', lang)}]")

            try:
                moon_raw = input(f"{get_text('system.select_moon', lang)} > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if moon_raw == "":
                moon = None
            else:
                try:
                    moon_idx = int(moon_raw) - 1
                    if 0 <= moon_idx < len(moons):
                        moon = moons[moon_idx]
                    else:
                        print(f"  {get_text('common.warning', lang)}")
                except ValueError:
                    print(f"  {get_text('common.warning', lang)}")

        try:
            steps = compute_route(system, destination=dest_body, moon=moon)
            _print_route(steps, lang)
        except ValueError as exc:
            print(f"{get_text('common.error', lang)}: {exc}", file=sys.stderr)

        # Ask whether to continue
        print()
        try:
            again = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if again not in ("y", "yes", ""):
            break

        # Re-print destination list
        print()
        _print_dest_list(ranked, parent, lang)


def _scan_mode(gamedata_path: Path, lang: str) -> None:
    """Scan GameData and start interactive mode.

    GameData/ をスキャンして天体ツリーを構築し、インタラクティブモードを開始する。

    Args:
        gamedata_path: Path to the GameData/ directory.
        lang: Language code for display strings.
    """
    if not gamedata_path.is_dir():
        print(
            f"{get_text('common.error', lang)}: "
            f"{get_text('error.file_not_found', lang)}: {gamedata_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"{get_text('system.scanning', lang)} {gamedata_path}")

    try:
        system = scan_configs(gamedata_path, output_dir=CELESTIAL_BODY_DIR)
    except ValueError as exc:
        print(f"{get_text('common.error', lang)}: {exc}", file=sys.stderr)
        sys.exit(1)

    n = len(system.bodies)
    print(f"  {n} {get_text('nav.bodies', lang)}")

    _interactive_mode(system, lang)


def _load_interactive(lang: str) -> None:
    """Load saved system data and start interactive.

    保存済みJSONデータを読み込んでインタラクティブモードを開始する。

    Args:
        lang: Language code for display strings.
    """
    try:
        system = load_system(CELESTIAL_BODY_DIR)
    except FileNotFoundError:
        print(
            f"{get_text('common.error', lang)}: "
            f"'{CELESTIAL_BODY_DIR}' {get_text('error.file_not_found', lang)}",
            file=sys.stderr,
        )
        print(
            "python run.py --scan <GameData_path>",
            file=sys.stderr,
        )
        sys.exit(1)
    except ValueError as exc:
        print(
            f"{get_text('common.error', lang)}: {get_text('error.parse_error', lang)}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"'{CELESTIAL_BODY_DIR}' -> {len(system.bodies)} {get_text('nav.bodies', lang)}")
    _interactive_mode(system, lang)


def main() -> None:
    """Entry point for the CLI.

    CLIのエントリポイント。argparseで引数を解析する。
    """
    parser = argparse.ArgumentParser(description="KSPDeltaVForMods")
    parser.add_argument("config", nargs="?", help="Kopernicus .cfg file")
    parser.add_argument("--scan", metavar="GAMEDATA", help="Scan GameData directory")
    parser.add_argument("--interactive", action="store_true", help="Load saved data")
    parser.add_argument(
        "--lang",
        choices=list(SUPPORTED_LANGUAGES),
        help="UI language (ja/en/id)",
    )
    args = parser.parse_args()

    lang = detect_language(override=args.lang)

    if args.scan:
        _scan_mode(Path(args.scan), lang)
        return

    if args.interactive:
        _load_interactive(lang)
        return

    if args.config is None:
        parser.print_help()
        sys.exit(1)

    # --- Single-cfg mode ---
    cfg_path = Path(args.config)

    if not cfg_path.exists():
        print(
            f"{get_text('common.error', lang)}: "
            f"{get_text('error.file_not_found', lang)}: {cfg_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        source = cfg_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"{get_text('common.error', lang)}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        bodies = parse_bodies(source, source_filename=cfg_path.stem)
    except Exception as exc:
        print(
            f"{get_text('common.error', lang)}: {get_text('error.parse_error', lang)}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not bodies:
        print(
            f"{get_text('common.warning', lang)}: {get_text('error.no_bodies', lang)}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"KSPDeltaVForMods \u2014 {cfg_path.name} ({len(bodies)} {get_text('nav.bodies', lang)})")
    print("=" * 50)

    for body in bodies:
        try:
            _print_body(body, lang)
        except Exception as exc:
            print(
                f"  {get_text('common.error', lang)}: {body.name}: {exc}",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
