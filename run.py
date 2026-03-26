"""Standalone CLI for KSP ΔV calculations from Kopernicus config files.

Kopernicus .cfg ファイルからΔV計算結果を表示するスタンドアロンCLI。
pip 不要。python run.py path/to/config.cfg で実行可能。

Usage:
    python run.py <config.cfg>           Single file analysis (existing mode)
    python run.py --scan <GameData_path> Scan GameData and start interactive mode
    python run.py --interactive          Load from celestial_body/ and start interactive
    python run.py --lang en <config.cfg> Specify language (ja/en/id)
    python run.py --detail --interactive Show detailed route info
    python run.py --format json ...      Output format (text/md/json)
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import signal
import sys
from pathlib import Path

from kopdeltav.calculator import (
    DvStep,
    LaunchResult,
    SegmentType,
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


# ---------------------------------------------------------------------------
# Terminal capability detection
# ---------------------------------------------------------------------------


def _supports_color() -> bool:
    """Detect if terminal supports ANSI color.

    ターミナルがANSIカラーをサポートするか検出する。

    Returns:
        True if ANSI color codes are likely supported.
    """
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if os.environ.get("NO_COLOR"):
        return False
    return os.environ.get("TERM", "") != "dumb"


def _supports_unicode() -> bool:
    """Detect if stdout encoding supports Unicode.

    stdout のエンコーディングがUnicodeを扱えるか検出する。

    Returns:
        True if stdout encoding contains 'utf'.
    """
    enc = getattr(sys.stdout, "encoding", "") or ""
    return "utf" in enc.lower()


def _enable_ansi_on_windows() -> None:
    """Enable ANSI escape codes on Windows 10+.

    Windows 10 以降でANSIエスケープコードを有効にする。
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


# SIGPIPE handling — allow clean exit when piped to head/less.
with contextlib.suppress(AttributeError, OSError):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)


# ---------------------------------------------------------------------------
# ANSI color system
# ---------------------------------------------------------------------------

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
    """Wrap text with ANSI color codes if color is enabled.

    カラー有効時にANSIカラーコードでテキストを装飾する。

    Args:
        text: The text to colorize.
        color_name: Key in _COLORS dict.
        use_color: Whether to apply color.

    Returns:
        Colored or plain text.
    """
    if not use_color:
        return text
    code = _COLORS.get(color_name, "")
    return f"{code}{text}{_COLORS['reset']}" if code else text


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


# ---------------------------------------------------------------------------
# Subway-map route renderer
# ---------------------------------------------------------------------------


def _format_transfer_time(seconds: float) -> str:
    """Format transfer time as human-readable days/hours string.

    遷移時間を日/時間の人間可読文字列にフォーマットする。

    Args:
        seconds: Transfer time in seconds.

    Returns:
        Formatted string like "42d 6h" or "3h 15m".
    """
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _print_subway_route(
    steps: list[DvStep],
    home_name: str,
    dest_name: str,
    lang: str,
    use_color: bool,
    use_unicode: bool,
    detail: bool = False,
) -> None:
    """Print a subway-map style ΔV route with Unicode/ASCII fallback.

    地下鉄路線図スタイルでΔVルートを表示する。Unicode/ASCIIフォールバック対応。

    Args:
        steps: Ordered list of DvStep objects.
        home_name: Display name of the origin body.
        dest_name: Display name of the destination body.
        lang: Language code.
        use_color: Whether to use ANSI colors.
        use_unicode: Whether to use Unicode symbols.
        detail: Whether to show expanded detail information.
    """
    if not steps:
        return

    # Symbol definitions
    if use_unicode:
        sym_solid = "\u25cf"  # ●
        sym_hollow = "\u25cb"  # ○
        sym_up = "\u25b2"  # ▲
        sym_down = "\u25bc"  # ▼
        sym_pipe = "\u2502"  # │
        sym_dash = "\u2500"  # ─
    else:
        sym_solid = "(*)"
        sym_hollow = "(o)"
        sym_up = "^"
        sym_down = "v"
        sym_pipe = "|"
        sym_dash = "-"

    # Header line
    header = f"{sym_dash}{sym_dash} \u0394V Route: {home_name} \u2192 {dest_name} "
    header += sym_dash * max(1, 50 - len(header))
    print()
    print(_color(header, "bold", use_color))
    print()

    # Starting node
    print(f"  {sym_solid} {home_name} (surface)")

    for i, step in enumerate(steps):
        seg_color = _SEGMENT_COLORS.get(step.segment_type.value, "reset")
        is_last = i == len(steps) - 1

        # Determine direction arrow: acceleration (launch/escape/transfer) vs deceleration
        if step.segment_type in (
            SegmentType.CAPTURE,
            SegmentType.LANDING,
            SegmentType.MOON_LANDING,
        ):
            arrow = sym_down
        else:
            arrow = sym_up

        # ΔV line
        dv_str = _fmt_number(step.dv, 0)
        dv_line = f"  {sym_pipe}  {arrow} {dv_str:>7} {get_text('common.unit_ms', lang)}"
        dv_line += f"   {step.label}"
        print(_color(dv_line, seg_color, use_color))

        # Detail sub-items (if enabled)
        if detail:
            _print_detail_block(step, lang, use_unicode, use_color)

        # Intermediate node (after each step except the very last LANDING)
        if not is_last:
            node_type = _node_after_step(step.segment_type)
            node_sym = sym_solid if node_type == "solid" else sym_hollow
            node_label = _node_label(step, lang)
            print(f"  {node_sym}{sym_dash} {node_label}")
        else:
            # Final destination node
            final_name = dest_name
            print(f"  {sym_solid} {final_name} (surface)")

    # Total line
    total_dv = _fmt_number(steps[-1].cumulative, 0)
    print()
    total_label = get_text("route.total", lang)
    unit = get_text("common.unit_ms", lang)
    print(f"  {total_label}: {_color(total_dv, 'bold', use_color)} {unit}")


def _node_after_step(seg_type: SegmentType) -> str:
    """Determine node type (solid/hollow) after a route segment.

    ルートセグメント後のノードタイプ(実線/中空)を決定する。

    Args:
        seg_type: The segment type.

    Returns:
        "solid" for stable positions, "hollow" for SOI boundaries.
    """
    if seg_type in (SegmentType.LAUNCH,):
        return "solid"  # Low orbit
    if seg_type in (SegmentType.ESCAPE, SegmentType.SYSTEM_ESCAPE):
        return "hollow"  # SOI edge
    if seg_type in (SegmentType.TRANSFER, SegmentType.MOON_TRANSFER):
        return "hollow"  # SOI edge
    if seg_type in (SegmentType.CAPTURE,):
        return "solid"  # Low orbit
    return "solid"


def _node_label(step: DvStep, lang: str) -> str:
    """Generate an appropriate label for the intermediate node after a step.

    ステップ後の中間ノードの適切なラベルを生成する。

    Args:
        step: The DvStep that was just completed.
        lang: Language code.

    Returns:
        A descriptive label for the node.
    """
    seg = step.segment_type
    if seg == SegmentType.LAUNCH:
        return "Low orbit"
    if seg in (SegmentType.ESCAPE, SegmentType.SYSTEM_ESCAPE):
        return "SOI edge"
    if seg in (SegmentType.TRANSFER, SegmentType.MOON_TRANSFER):
        return "SOI edge"
    if seg == SegmentType.CAPTURE:
        return "Low orbit"
    return step.label


def _print_detail_block(
    step: DvStep,
    lang: str,
    use_unicode: bool,
    use_color: bool,
) -> None:
    """Print detail sub-items for a route step using tree connectors.

    ルートステップの詳細サブ項目をツリーコネクタ付きで表示する。

    Args:
        step: The DvStep to show details for.
        lang: Language code.
        use_unicode: Whether to use Unicode box-drawing characters.
        use_color: Whether to use ANSI color.
    """
    if use_unicode:
        sym_pipe = "\u2502"  # │
        sym_corner = "\u2514"  # └
    else:
        sym_pipe = "|"
        sym_corner = "\\"

    # Display note for any segment type that has one.
    if step.note:
        print(f"  {sym_pipe}  {sym_corner} {step.note}")


# ---------------------------------------------------------------------------
# Output format: JSON
# ---------------------------------------------------------------------------


def _route_to_json(steps: list[DvStep], home_name: str, dest_name: str) -> str:
    """Serialize a ΔV route to JSON format.

    ΔVルートをJSON形式にシリアライズする。

    Args:
        steps: Ordered list of DvStep objects.
        home_name: Origin body name.
        dest_name: Destination body name.

    Returns:
        JSON string with route data.
    """
    segments = []
    for step in steps:
        seg: dict[str, object] = {
            "label": step.label,
            "dv": round(step.dv, 1),
            "cumulative": round(step.cumulative, 1),
            "type": step.segment_type.value,
        }
        if step.note:
            seg["note"] = step.note
        segments.append(seg)

    total_dv = round(steps[-1].cumulative, 1) if steps else 0.0
    data = {
        "route": {
            "from": home_name,
            "to": dest_name,
            "total_dv": total_dv,
            "segments": segments,
        }
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Output format: Markdown
# ---------------------------------------------------------------------------


def _route_to_markdown(
    steps: list[DvStep],
    home_name: str,
    dest_name: str,
    lang: str,
) -> str:
    """Render a ΔV route as a Markdown table.

    ΔVルートをMarkdownテーブルとして整形する。

    Args:
        steps: Ordered list of DvStep objects.
        home_name: Origin body name.
        dest_name: Destination body name.
        lang: Language code.

    Returns:
        Markdown-formatted string.
    """
    step_hdr = get_text("route.step", lang)
    dv_hdr = get_text("route.dv", lang)
    cumul_hdr = get_text("route.cumulative", lang)
    lines = [
        f"## \u0394V Route: {home_name} \u2192 {dest_name}",
        "",
        f"| # | {step_hdr} | {dv_hdr} | {cumul_hdr} |",
        "|---|---|---|---|",
    ]
    for i, step in enumerate(steps, 1):
        dv_str = _fmt_number(step.dv, 0)
        cumul_str = _fmt_number(step.cumulative, 0)
        note = f" ({step.note})" if step.note else ""
        lines.append(f"| {i} | {step.label}{note} | {dv_str} m/s | {cumul_str} m/s |")

    if steps:
        total = _fmt_number(steps[-1].cumulative, 0)
        total_label = get_text("route.total", lang)
        lines.append("")
        lines.append(f"**{total_label}**: {total} m/s")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Route display dispatcher
# ---------------------------------------------------------------------------


def _display_route(
    steps: list[DvStep],
    home_name: str,
    dest_name: str,
    lang: str,
    use_color: bool,
    use_unicode: bool,
    detail: bool,
    output_format: str,
) -> None:
    """Display a route in the selected format.

    選択されたフォーマットでルートを表示する。

    Args:
        steps: Ordered list of DvStep objects.
        home_name: Origin body display name.
        dest_name: Destination body display name.
        lang: Language code.
        use_color: Whether to use ANSI colors.
        use_unicode: Whether to use Unicode symbols.
        detail: Whether to show detail blocks.
        output_format: One of "text", "md", "json".
    """
    if output_format == "json":
        print(_route_to_json(steps, home_name, dest_name))
    elif output_format == "md":
        print(_route_to_markdown(steps, home_name, dest_name, lang))
    else:
        _print_subway_route(steps, home_name, dest_name, lang, use_color, use_unicode, detail)


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


def _interactive_mode(
    system: CelestialSystem,
    lang: str,
    use_color: bool = True,
    use_unicode: bool = True,
    detail: bool = False,
    output_format: str = "text",
) -> None:
    """Interactive ΔV map navigator using input().

    input() を使ったインタラクティブΔVマップナビゲーター。

    Args:
        system: The celestial system to navigate.
        lang: Language code for display strings.
        use_color: Whether to use ANSI colors.
        use_unicode: Whether to use Unicode symbols.
        detail: Whether to show detail blocks in route output.
        output_format: Output format ("text", "md", "json").
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
                home_disp = home.display_name
                dest_disp = parent.name if parent else "System"
                _display_route(
                    steps,
                    home_disp,
                    dest_disp,
                    lang,
                    use_color,
                    use_unicode,
                    detail,
                    output_format,
                )
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
            final_dest = moon if moon else dest_body
            home_disp = home.display_name
            dest_disp = final_dest.display_name
            _display_route(
                steps,
                home_disp,
                dest_disp,
                lang,
                use_color,
                use_unicode,
                detail,
                output_format,
            )
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


def _scan_mode(
    gamedata_path: Path,
    lang: str,
    use_color: bool = True,
    use_unicode: bool = True,
    detail: bool = False,
    output_format: str = "text",
) -> None:
    """Scan GameData and start interactive mode.

    GameData/ をスキャンして天体ツリーを構築し、インタラクティブモードを開始する。

    Args:
        gamedata_path: Path to the GameData/ directory.
        lang: Language code for display strings.
        use_color: Whether to use ANSI colors.
        use_unicode: Whether to use Unicode symbols.
        detail: Whether to show detail blocks.
        output_format: Output format ("text", "md", "json").
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

    _interactive_mode(system, lang, use_color, use_unicode, detail, output_format)


def _load_interactive(
    lang: str,
    use_color: bool = True,
    use_unicode: bool = True,
    detail: bool = False,
    output_format: str = "text",
) -> None:
    """Load saved system data and start interactive.

    保存済みJSONデータを読み込んでインタラクティブモードを開始する。

    Args:
        lang: Language code for display strings.
        use_color: Whether to use ANSI colors.
        use_unicode: Whether to use Unicode symbols.
        detail: Whether to show detail blocks.
        output_format: Output format ("text", "md", "json").
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
    _interactive_mode(system, lang, use_color, use_unicode, detail, output_format)


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
    parser.add_argument("--detail", action="store_true", help="Show detailed route info")
    parser.add_argument(
        "--format",
        choices=["text", "md", "json"],
        default="text",
        dest="output_format",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    lang = detect_language(override=args.lang)

    # Detect terminal capabilities
    _enable_ansi_on_windows()
    use_color = _supports_color()
    use_unicode = _supports_unicode()
    detail: bool = args.detail
    output_format: str = args.output_format

    if args.scan:
        _scan_mode(Path(args.scan), lang, use_color, use_unicode, detail, output_format)
        return

    if args.interactive:
        _load_interactive(lang, use_color, use_unicode, detail, output_format)
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
