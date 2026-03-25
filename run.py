"""Standalone CLI for KSP ΔV calculations from Kopernicus config files.

Kopernicus .cfg ファイルからΔV計算結果を表示するスタンドアロンCLI。
pip 不要。python run.py path/to/config.cfg で実行可能。
"""

from __future__ import annotations

import sys
from pathlib import Path

from kopdeltav.calculator import (
    LaunchResult,
    calculate_launch,
    escape_velocity,
    low_orbit_altitude,
    surface_density,
)
from kopdeltav.models import CelestialBody
from kopdeltav.parser import parse_bodies


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


def main() -> None:
    """Entry point for the CLI.

    CLIのエントリポイント。引数なしの場合は使用方法を表示する。
    """
    if len(sys.argv) < 2:
        print("使用方法: python run.py <config.cfg>")
        print("例:       python run.py sample_configs/Sanctar.cfg")
        sys.exit(1)

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
