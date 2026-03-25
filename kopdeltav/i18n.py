"""Bilingual translation system for CLI and backend output.

日英バイリンガル翻訳モジュール。外部依存なし。
"""

from __future__ import annotations

SUPPORTED_LANGUAGES: tuple[str, ...] = ("ja", "en")
DEFAULT_LANGUAGE: str = "ja"

_TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = {
    "ja": {
        "nav": {
            "title": "KSPDeltaVForMods",
            "bodies": "天体一覧",
        },
        "body": {
            "name": "天体名",
            "radius": "半径",
            "mass": "質量",
            "gravity": "表面重力",
            "atmosphere": "大気",
            "has_atmosphere": "大気あり",
            "no_atmosphere": "大気なし",
            "has_ocean": "海洋あり",
            "no_ocean": "海洋なし",
        },
        "launch": {
            "title": "低軌道投入ΔV",
            "orbital_velocity": "軌道速度",
            "gravity_loss": "重力損失",
            "drag_loss": "大気抵抗損失",
            "total_ideal": "理論最小ΔV",
            "total_rocket": "ロケットΔV（実用値）",  # noqa: RUF001
            "jet_savings": "ジェット節約分",
            "total_with_jets": "ジェット併用ΔV",
            "target_altitude": "目標高度",
            "geostationary": "静止軌道遷移",
            "geostationary_altitude": "静止軌道高度",
        },
        "hohmann": {
            "title": "ホーマン遷移",
            "departure_dv": "出発ΔV",
            "arrival_dv": "到着ΔV",
            "total_dv": "合計ΔV",
            "transfer_time": "遷移時間",
        },
        "tsiolkovsky": {
            "title": "ツィオルコフスキーの公式",
            "mass_ratio": "質量比",
            "fuel_fraction": "燃料割合",
            "dry_mass": "乾燥質量",
            "fuel_mass": "燃料質量",
            "delta_v": "ΔV",
            "isp": "比推力",
            "wet_mass": "湿潤質量",
        },
        "atmosphere": {
            "title": "大気プロファイル",
            "depth": "大気高度上限",
            "sea_level_pressure": "海面気圧",
            "sea_level_temperature": "海面温度",
            "sea_level_density": "海面大気密度",
            "molar_mass": "モル質量",
            "adiabatic_index": "断熱指数",
        },
        "common": {
            "calculate": "計算",
            "reset": "リセット",
            "error": "エラー",
            "warning": "警告",
            "unit_m": "m",
            "unit_ms": "m/s",
            "unit_s": "秒",
            "unit_kg": "kg",
            "unit_kgm3": "kg/m³",
            "unit_kpa": "kPa",
            "unit_k": "K",
        },
        "route": {
            "launch": "低軌道投入",
            "escape": "母星脱出",
            "transfer": "惑星間遷移",
            "orbit_insertion": "軌道投入",
            "landing": "着陸",
            "moon_transfer": "衛星遷移",
            "moon_landing": "衛星着陸",
            "system_escape": "恒星系脱出",
            "third_cosmic": "第三宇宙速度",
            "powered_landing": "パワード着陸",
            "aerobrake_landing": "エアロブレーキ着陸",
            "cumulative": "累積ΔV",
        },
        "system": {
            "home_world": "母星",
            "star": "恒星",
            "planets": "惑星一覧",
            "moons": "衛星一覧",
            "select_destination": "遷移先を選択",
            "select_moon": "衛星を選択",
            "press_enter_escape": "Enterで恒星系脱出",
            "press_enter_land": "Enterで着陸",
            "no_bodies": "天体が見つかりません",
            "scanning": "GameDataをスキャン中...",
        },
        "error": {
            "file_not_found": "ファイルが見つかりません",
            "parse_error": "設定ファイルの解析に失敗しました",
            "no_bodies": "天体が見つかりません",
            "invalid_altitude": "高度は非負でなければなりません",
        },
    },
    "en": {
        "nav": {
            "title": "KSPDeltaVForMods",
            "bodies": "Celestial Bodies",
        },
        "body": {
            "name": "Body Name",
            "radius": "Radius",
            "mass": "Mass",
            "gravity": "Surface Gravity",
            "atmosphere": "Atmosphere",
            "has_atmosphere": "Has Atmosphere",
            "no_atmosphere": "No Atmosphere",
            "has_ocean": "Has Ocean",
            "no_ocean": "No Ocean",
        },
        "launch": {
            "title": "Launch to Low Orbit ΔV",
            "orbital_velocity": "Orbital Velocity",
            "gravity_loss": "Gravity Loss",
            "drag_loss": "Drag Loss",
            "total_ideal": "Theoretical Minimum ΔV",
            "total_rocket": "Rocket ΔV (Practical)",
            "jet_savings": "Jet Engine Savings",
            "total_with_jets": "ΔV with Jets",
            "target_altitude": "Target Altitude",
            "geostationary": "Geostationary Transfer",
            "geostationary_altitude": "Geostationary Altitude",
        },
        "hohmann": {
            "title": "Hohmann Transfer",
            "departure_dv": "Departure ΔV",
            "arrival_dv": "Arrival ΔV",
            "total_dv": "Total ΔV",
            "transfer_time": "Transfer Time",
        },
        "tsiolkovsky": {
            "title": "Tsiolkovsky Rocket Equation",
            "mass_ratio": "Mass Ratio",
            "fuel_fraction": "Fuel Fraction",
            "dry_mass": "Dry Mass",
            "fuel_mass": "Fuel Mass",
            "delta_v": "ΔV",
            "isp": "Specific Impulse",
            "wet_mass": "Wet Mass",
        },
        "atmosphere": {
            "title": "Atmosphere Profile",
            "depth": "Atmosphere Ceiling",
            "sea_level_pressure": "Sea Level Pressure",
            "sea_level_temperature": "Sea Level Temperature",
            "sea_level_density": "Sea Level Density",
            "molar_mass": "Molar Mass",
            "adiabatic_index": "Adiabatic Index",
        },
        "common": {
            "calculate": "Calculate",
            "reset": "Reset",
            "error": "Error",
            "warning": "Warning",
            "unit_m": "m",
            "unit_ms": "m/s",
            "unit_s": "s",
            "unit_kg": "kg",
            "unit_kgm3": "kg/m³",
            "unit_kpa": "kPa",
            "unit_k": "K",
        },
        "route": {
            "launch": "Launch to Low Orbit",
            "escape": "Escape Home World",
            "transfer": "Interplanetary Transfer",
            "orbit_insertion": "Orbit Insertion",
            "landing": "Landing",
            "moon_transfer": "Moon Transfer",
            "moon_landing": "Moon Landing",
            "system_escape": "Star System Escape",
            "third_cosmic": "Third Cosmic Velocity",
            "powered_landing": "Powered Landing",
            "aerobrake_landing": "Aerobrake Landing",
            "cumulative": "Cumulative ΔV",
        },
        "system": {
            "home_world": "Home World",
            "star": "Star",
            "planets": "Planets",
            "moons": "Moons",
            "select_destination": "Select destination",
            "select_moon": "Select moon",
            "press_enter_escape": "Press Enter for system escape",
            "press_enter_land": "Press Enter to land",
            "no_bodies": "No celestial bodies found",
            "scanning": "Scanning GameData...",
        },
        "error": {
            "file_not_found": "File not found",
            "parse_error": "Failed to parse configuration file",
            "no_bodies": "No celestial bodies found",
            "invalid_altitude": "Altitude must be non-negative",
        },
    },
}


def get_text(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Get translated text by dot-notation key.

    翻訳文字列を取得する。

    Args:
        key: Dot-notation key (e.g. "launch.title", "common.calculate").
        lang: Language code ("ja" or "en"). Falls back to DEFAULT_LANGUAGE
              if the language is not supported.

    Returns:
        Translated string. Returns the key itself if not found.
    """
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    parts = key.split(".", maxsplit=1)
    if len(parts) != 2:
        return key

    category, name = parts
    lang_dict = _TRANSLATIONS[lang]
    category_dict = lang_dict.get(category)
    if category_dict is None:
        return key

    return category_dict.get(name, key)


def get_all_keys(lang: str = DEFAULT_LANGUAGE) -> dict[str, str]:
    """Get all translation keys flattened to dot-notation.

    全翻訳キーをフラット化して返す。

    Args:
        lang: Language code ("ja" or "en"). Falls back to DEFAULT_LANGUAGE
              if the language is not supported.

    Returns:
        Dict mapping dot-notation keys to translated strings.
    """
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    result: dict[str, str] = {}
    for category, entries in _TRANSLATIONS[lang].items():
        for name, value in entries.items():
            result[f"{category}.{name}"] = value
    return result
