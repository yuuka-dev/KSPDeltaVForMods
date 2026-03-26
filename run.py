"""Standalone CLI for KSP ΔV calculations from Kopernicus config files.

Kopernicus .cfg ファイルからΔV計算結果を表示するスタンドアロンCLI。
pip 不要。python run.py path/to/config.cfg で実行可能。

Usage:
    python run.py <config.cfg>           Single file analysis (existing mode)
    python run.py --scan <GameData_path> Scan GameData and start interactive mode
    python run.py --interactive          Load from celestial_body/ and start interactive
"""

from __future__ import annotations

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
from kopdeltav.models import CelestialBody
from kopdeltav.parser import parse_bodies
from kopdeltav.system import CelestialSystem, build_tree, scan_configs, sort_by_transfer_dv

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


def _print_body(body: CelestialBody) -> None:
    """Print formatted ΔV information for a single celestial body.

    天体のΔV情報を整形して出力する。

    Args:
        body: The celestial body to display.
    """
    # Header
    display = body.display_name if body.display_name != body.name else body.name
    if display != body.name:
        print(f"\n=== {body.name} ({display}) ===")
    else:
        print(f"\n=== {body.name} ===")

    # Basic properties
    v_esc = escape_velocity(body, 0.0)
    print(f"  半径:           {_fmt_number(body.radius)} m")
    print(f"  表面重力:       {body.gee_asl:.2f} g")
    print(f"  μ:              {body.mu:.4e} m³/s²")
    print(f"  脱出速度:       {_fmt_number(v_esc, 1)} m/s")

    # Atmosphere
    if body.atmosphere is not None:
        atmo = body.atmosphere
        rho = surface_density(body)
        print()
        print("  [大気]")
        print(f"  大気高度上限:   {_fmt_number(atmo.atmosphere_depth)} m")
        print(f"  海面気圧:       {atmo.pressure_at_sea_level:.1f} kPa")
        print(f"  海面温度:       {atmo.temperature_at_sea_level:.1f} K")
        if rho is not None:
            print(f"  海面密度:       {rho:.3f} kg/m³")

    # Orbit
    if body.orbit is not None:
        orb = body.orbit
        print()
        print("  [軌道]")
        print(f"  軌道長半径:     {_fmt_number(orb.semi_major_axis)} m")
        print(f"  離心率:         {orb.eccentricity:.5f}")
        print(f"  軌道傾斜角:     {orb.inclination:.2f}°")

    # Launch ΔV
    alt = low_orbit_altitude(body)
    result: LaunchResult = calculate_launch(body, alt)
    print()
    print(f"  [低軌道投入ΔV] (高度: {_fmt_number(alt)} m)")
    print(f"  軌道速度:       {_fmt_number(result.orbital_velocity, 1)} m/s")
    print(f"  重力損失:       {_fmt_number(result.gravity_loss, 1)} m/s")
    print(f"  大気抵抗損失:   {_fmt_number(result.drag_loss, 1)} m/s")
    print(f"  ロケットΔV:     ≈{_fmt_number(result.total_rocket, 0)} m/s")
    if result.jet_savings > 0:
        print(f"  ジェット併用ΔV: ≈{_fmt_number(result.total_with_jets, 0)} m/s")

    print()


def _print_home_info(system: CelestialSystem) -> None:
    """Print home world summary with geostationary and escape info.

    ホームワールドの概要(静止軌道・脱出速度含む)を表示する。

    Args:
        system: The celestial system containing the home world.
    """
    home = system.home_world
    alt = low_orbit_altitude(home)
    result = calculate_launch(home, alt)

    print("\n=== 恒星系 ===")
    display = home.display_name if home.display_name != home.name else home.name
    label = f"{home.name} ({display})" if display != home.name else home.name
    radius_str = _fmt_number(home.radius)
    print(f"ホームワールド: {label} (半径: {radius_str} m, 重力: {home.gee_asl:.1f}g)")
    print()

    # Low orbit
    rocket_str = f"≈{_fmt_number(result.total_rocket, 0)} m/s (ロケット)"
    if result.jet_savings > 0:
        jet_str = f" / ≈{_fmt_number(result.total_with_jets, 0)} m/s (ジェット)"
    else:
        jet_str = ""
    print(f"[低軌道]  {rocket_str}{jet_str}")

    # Geostationary
    try:
        geo_alt = geostationary_altitude(home)
        geo = geostationary_dv(home)
        print(
            f"[静止軌道] (高度: {_fmt_number(geo_alt)} m)  ΔV: {_fmt_number(geo.total_dv, 0)} m/s"
        )
    except ValueError:
        print("[静止軌道] 計算不可(自転周期不明)")

    # Escape from low orbit
    esc_dv = escape_dv_from_low_orbit(home)
    print(f"[脱出]    ΔV: {_fmt_number(esc_dv, 0)} m/s")


def _print_route(steps: list[DvStep]) -> None:
    """Print ΔV route with cumulative totals.

    ΔVルートを累積値とともに表示する。

    Args:
        steps: Ordered list of DvStep objects representing each maneuver.
    """
    print()
    print("--- ΔVルート ---")
    for i, step in enumerate(steps, 1):
        note_str = f"  ({step.note})" if step.note else ""
        print(
            f"  {i:2d}. {step.label:<35}"
            f"  {_fmt_number(step.dv, 0):>8} m/s"
            f"  [累計: {_fmt_number(step.cumulative, 0)} m/s]{note_str}"
        )
    if steps:
        print(f"\n  合計ΔV: {_fmt_number(steps[-1].cumulative, 0)} m/s")


def _interactive_mode(system: CelestialSystem) -> None:
    """Interactive ΔV map navigator using input().

    input() を使ったインタラクティブΔVマップナビゲーター。

    Args:
        system: The celestial system to navigate.
    """
    home = system.home_world
    parent = home.parent

    _print_home_info(system)

    # Build list of sibling planets (bodies orbiting same parent as home)
    if parent is not None:
        siblings = [b for b in parent.children if b is not home]
        ranked = sort_by_transfer_dv(home, siblings)
    else:
        ranked = []

    print()
    print("目的地を選択してください:")
    for i, (body, dv) in enumerate(ranked, 1):
        display = body.display_name if body.display_name != body.name else body.name
        label = f"{body.name} ({display})" if display != body.name else body.name
        print(f"  {i}) {label:<30}  (ΔV: {_fmt_number(dv, 0)} m/s)")
    print("  [Enter] 第三宇宙速度(恒星系脱出)")
    print("  q) 終了")

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
                _print_route(steps)
            except ValueError as exc:
                print(f"エラー: {exc}", file=sys.stderr)
            continue

        # Numeric selection
        try:
            idx = int(raw) - 1
        except ValueError:
            print("  番号を入力するか、Enterで恒星系脱出、qで終了してください。")
            continue

        if idx < 0 or idx >= len(ranked):
            print(f"  1〜{len(ranked)} の番号を入力してください。")
            continue

        dest_body, _ = ranked[idx]

        # Ask for moon selection if destination has children
        moons = dest_body.children
        moon: CelestialBody | None = None

        if moons:
            print(f"\n{dest_body.name} の衛星:")
            for j, m in enumerate(moons, 1):
                m_display = m.display_name if m.display_name != m.name else m.name
                m_label = f"{m.name} ({m_display})" if m_display != m.name else m.name
                print(f"  {j}) {m_label}")
            print("  [Enterキー] 惑星本体")

            try:
                moon_raw = input("衛星番号 > ").strip()
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
                        print("  無効な番号です。惑星本体への経路を表示します。")
                except ValueError:
                    print("  無効な入力です。惑星本体への経路を表示します。")

        try:
            steps = compute_route(system, destination=dest_body, moon=moon)
            _print_route(steps)
        except ValueError as exc:
            print(f"エラー: {exc}", file=sys.stderr)

        # Ask whether to continue
        print()
        print("別の目的地を選びますか? (y/n)")
        try:
            again = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if again not in ("y", "yes", ""):
            break

        # Re-print destination list
        print()
        print("目的地を選択してください:")
        for i, (body, dv) in enumerate(ranked, 1):
            display = body.display_name if body.display_name != body.name else body.name
            label = f"{body.name} ({display})" if display != body.name else body.name
            print(f"  {i}) {label:<30}  (ΔV: {_fmt_number(dv, 0)} m/s)")
        print("  [Enter] 第三宇宙速度(恒星系脱出)")
        print("  q) 終了")


def _scan_mode(gamedata_path: Path) -> None:
    """Scan GameData and start interactive mode.

    GameData/ をスキャンして天体ツリーを構築し、インタラクティブモードを開始する。

    Args:
        gamedata_path: Path to the GameData/ directory.
    """
    if not gamedata_path.is_dir():
        print(f"エラー: ディレクトリが見つかりません: {gamedata_path}", file=sys.stderr)
        sys.exit(1)

    print(f"スキャン中: {gamedata_path}")
    print(f"有効な設定ファイルを {CELESTIAL_BODY_DIR} にコピーします...")

    try:
        system = scan_configs(gamedata_path, output_dir=CELESTIAL_BODY_DIR)
    except ValueError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        sys.exit(1)

    n = len(system.bodies)
    print(f"  {n} 天体を読み込みました。")

    _interactive_mode(system)


def _load_interactive() -> None:
    """Load from celestial_body/ and start interactive.

    celestial_body/ ディレクトリのデータを読み込んでインタラクティブモードを開始する。
    """
    if not CELESTIAL_BODY_DIR.is_dir():
        print(
            f"エラー: '{CELESTIAL_BODY_DIR}' ディレクトリが見つかりません。",
            file=sys.stderr,
        )
        print(
            "先に 'python run.py --scan <GameData_path>' を実行してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    cfg_files = list(CELESTIAL_BODY_DIR.glob("*.cfg"))
    if not cfg_files:
        print(
            f"エラー: '{CELESTIAL_BODY_DIR}' に .cfg ファイルが見つかりません。",
            file=sys.stderr,
        )
        sys.exit(1)

    all_bodies: list[CelestialBody] = []
    for cfg_path in sorted(cfg_files):
        try:
            source = cfg_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"警告: {cfg_path} の読み込みに失敗しました: {exc}", file=sys.stderr)
            continue

        bodies = parse_bodies(source)
        all_bodies.extend(bodies)

    if not all_bodies:
        print("エラー: 天体が見つかりませんでした。", file=sys.stderr)
        sys.exit(1)

    try:
        system = build_tree(all_bodies)
    except ValueError as exc:
        print(f"エラー: 天体ツリーの構築に失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"'{CELESTIAL_BODY_DIR}' から {len(system.bodies)} 天体を読み込みました。")
    _interactive_mode(system)


def main() -> None:
    """Entry point for the CLI.

    CLIのエントリポイント。引数なしの場合は使用方法を表示する。
    """
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python run.py <config.cfg>           # 単一ファイル解析")
        print("  python run.py --scan <GameData_path> # GameData スキャン&インタラクティブ")
        print("  python run.py --interactive           # 保存済みデータから起動")
        sys.exit(1)

    if sys.argv[1] == "--scan":
        if len(sys.argv) < 3:
            print("エラー: --scan には GameData パスが必要です。", file=sys.stderr)
            print("例: python run.py --scan /path/to/KSP/GameData", file=sys.stderr)
            sys.exit(1)
        _scan_mode(Path(sys.argv[2]))
        return

    if sys.argv[1] == "--interactive":
        _load_interactive()
        return

    # --- Existing single-cfg mode ---
    cfg_path = Path(sys.argv[1])

    if not cfg_path.exists():
        print(f"エラー: ファイルが見つかりません: {cfg_path}", file=sys.stderr)
        sys.exit(1)

    try:
        source = cfg_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"エラー: ファイルの読み込みに失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        bodies = parse_bodies(source)
    except Exception as exc:
        print(f"エラー: 設定ファイルの解析に失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)

    if not bodies:
        print("警告: 天体が見つかりませんでした。", file=sys.stderr)
        sys.exit(1)

    print(f"KSPDeltaVForMods — {cfg_path.name} ({len(bodies)} 天体)")
    print("=" * 50)

    for body in bodies:
        try:
            _print_body(body)
        except Exception as exc:
            print(f"  エラー: {body.name} の計算に失敗しました: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
